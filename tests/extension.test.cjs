const test = require('node:test');
const assert = require('node:assert/strict');
const {createHmac, createHash} = require('node:crypto');
const core = require('../extension/lib/core.js');
const {stretch} = require('../extension/lib/audio.js');
const captions = require('../extension/lib/captions.js');

test('caption lookup failure never authorizes ASR; only confirmed absence does', () => {
  const id = '3BndvjrGwyE';
  for (const value of [null, {}, {videoId:id,state:'unknown'},
    {videoId:id,state:'unavailable',trackCount:21}, {videoId:id,state:'absent'},
    {videoId:'different',state:'absent',confirmed:true,trackCount:0},
    {videoId:id,state:'ready',cues:[]}]) {
    assert.throws(()=>captions.acquisition(value,id,core.cues));
  }
  assert.equal(captions.acquisition({videoId:id,state:'absent',confirmed:true,trackCount:0},id,core.cues),null);
  const result = captions.acquisition({videoId:id,state:'ready',language:'en',cues:[{start:0,end:2,text:'Hello'}]},id,core.cues);
  assert.equal(result.cues.length,1);
  assert.equal(result.language,'en');
});

test('choose the active caption language instead of the first dubbed-audio track', () => {
  const tracks=[{languageCode:'ar',kind:'asr'},{languageCode:'en',kind:'asr'},{languageCode:'en'}];
  assert.equal(captions.selectTrack(tracks,{languageCode:'en',kind:'asr'},null,0),tracks[1]);
  assert.equal(captions.selectTrack(tracks,null,'en',0),tracks[2]);
  assert.equal(captions.selectTrack(tracks,null,null,1),tracks[1]);
});

test('JSON3 captions preserve times, join tokens and ignore window control events', () => {
  const rows=captions.json3({events:[{tStartMs:0,wWinId:1},
    {tStartMs:1000,dDurationMs:2000,segs:[{utf8:'Hello '},{utf8:'world'}]},
    {tStartMs:2000,dDurationMs:2000,aAppend:1,segs:[{utf8:'again'}]},
    {tStartMs:4000,dDurationMs:1500,segs:[{utf8:'Next'}]}]});
  assert.deepEqual(rows,[{start:1,end:4,text:'Hello world again'},{start:4,end:5.5,text:'Next'}]);
  assert.throws(()=>captions.json3({events:[{tStartMs:0,segs:[{utf8:'No timing'}]}]}));
});

test('signed requests match backend HMAC contract', async () => {
  const session = {request_key: 'ab'.repeat(32), token: 'test'};
  const headers = await core.signedHeaders(session, 'POST', '/v1/jobs', '{"text":"hello"}');
  const message = ['POST', '/v1/jobs', createHash('sha256').update('{"text":"hello"}').digest('hex'), headers['X-Auvirel-Time'], headers['X-Auvirel-Nonce']].join('\n');
  assert.equal(headers['X-Auvirel-Signature'], createHmac('sha256', Buffer.from(session.request_key, 'hex')).update(message).digest('hex'));
});
test('SRT timing and invalid input', () => {
  const result = core.parseSrt('1\r\n00:00:01,000 --> 00:00:02,250\r\n<b>Hello</b>\r\n');
  assert.deepEqual(result, [{id: 0, start: 1, end: 2.25, text: 'Hello'}]);
  assert.throws(() => core.parseSrt('1\n00:61:00,000 --> 00:62:00,000\nhello'));
  assert.throws(() => core.cues([{start: 2, end: 1, text: 'hello'}]));
  assert.equal(core.atTime([{start: 1}, {start: 3}, {start: 5}], 4), 1);
});
test('endpoint and Modal command validation', () => {
  assert.equal(core.endpoint('https://sample.modal.run/', true), 'https://sample.modal.run');
  for (const value of ['http://sample.modal.run', 'https://sample.modal.run.evil.org', 'https://user:password@sample.modal.run']) assert.throws(() => core.endpoint(value, true));
  assert.deepEqual(core.parseModal('modal token set --token-id ak-abc --token-secret as-def --profile=x'), {token_id: 'ak-abc', token_secret: 'as-def'});
});
test('WSOLA changes duration while retaining sine pitch and finite output', async () => {
  const rate = 24000, frequency = 220;
  const input = Float32Array.from({length: rate * 2}, (_, i) => .4 * Math.sin(2 * Math.PI * frequency * i / rate));
  for (const speed of [.7, 1.3, 1.8]) {
    const output = await stretch(input, speed, rate);
    assert.equal(output.length, Math.round(input.length / speed));
    assert.ok(output.every(Number.isFinite));
    let crossings = 0; const start = Math.floor(rate * .15), end = output.length - start;
    for (let i = start + 1; i < end; i++) if (output[i - 1] < 0 && output[i] >= 0) crossings++;
    assert.ok(Math.abs(crossings * rate / (end - start) - frequency) < 8);
    assert.equal(output[0], 0);
  }
});
test('WSOLA cancellation stops expensive processing', async () => {
  await assert.rejects(stretch(new Float32Array(24000), 1.5, 24000, () => true), {name: 'AbortError'});
});
