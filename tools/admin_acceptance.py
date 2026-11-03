"""Verify the deployed private admin UI and ticket lifecycle over Tailscale."""
import json
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright
from vps import connection
from smoke_backend import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    _, destination = connection()
    origin = 'http://' + destination.split('@')[1] + ':8001'
    env = dict(line.split('=', 1) for line in (ROOT / '.private/deployment/server.env').read_text().splitlines() if '=' in line)
    token = env['AUVIREL_ADMIN_TOKEN']
    public = Client()
    report = {'checks': []}
    with httpx.Client(timeout=30, headers={'Authorization': 'Bearer '+token}) as client:
        assert httpx.get(origin+'/admin/tickets').status_code == 401
        response = client.post(origin+'/admin/tickets', json={'label': 'Acceptance lifecycle', 'duration': 60})
        response.raise_for_status()
        ticket = response.json()
        activated = public.http.post(public.origin+'/v1/session', json={'code': ticket['code']})
        activated.raise_for_status()
        before = activated.json()['ticket_expires']
        client.patch(origin+'/admin/tickets/'+ticket['id'], json={'extend_seconds': 60}).raise_for_status()
        extended = public.http.post(public.origin+'/v1/session', json={'code': ticket['code']})
        extended.raise_for_status()
        assert extended.json()['ticket_expires'] >= before+59
        client.patch(origin+'/admin/tickets/'+ticket['id'], json={'active': False}).raise_for_status()
        assert public.http.post(public.origin+'/v1/session', json={'code': ticket['code']}).status_code == 401
        client.delete(origin+'/admin/tickets/'+ticket['id']).raise_for_status()
        report['checks'].append('Admin authentication; create/activate/extend/revoke/delete owned test ticket')
        stats = client.get(origin+'/admin/stats').json()
        keys = client.get(origin+'/admin/keys').json()
        assert len(keys) == 132
        assert all('encrypted' not in key for key in keys)
        report.update(key_records=len(keys), disk_free_bytes=stats['system']['disk_free'], cache=stats['cache'])
        report['balance_observations'] = {provider: {'known': sum(key['balance'] is not None for key in keys if key['provider'] == provider),
                                                  'total': sum(key['provider'] == provider for key in keys)} for provider in {key['provider'] for key in keys}}
        assert public.http.get(public.origin+'/admin/tickets').status_code == 404
        report['checks'].append('No admin route on public API; encrypted provider material absent from admin key response')
    output = ROOT / '.private/admin-qa'
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin)
        page.locator('#admin-token').fill(token)
        page.locator('#login-form button').click()
        page.locator('#workspace').wait_for(state='visible')
        page.screenshot(path=str(output/'dashboard.png'), full_page=True)
        page.locator('[data-tab="keys"]').click()
        assert page.locator('#keys tr').count() == 132
        page.locator('[data-tab="models"]').click()
        page.locator('#load-models').click()
        page.locator('#model-form').wait_for(state='visible')
        assert page.locator('[name="basic"] option').count() > 0
        report['checks'].append('Admin browser UI: login, metrics, all keys and live official model catalogs')
        assert not errors
        browser.close()
    report['passed'] = True
    (ROOT/'research/admin-acceptance.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
