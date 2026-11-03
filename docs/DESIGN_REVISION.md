# Veloa interface revision - 2026-11-03

## Reference comparison

Reviewed the supplied `Neko Dub/popup.html` and packaged popup styles, plus
`Youtube Dubbing/popup.html`, `popup-ui-polish.js`, `popup-settings-integrated.js`
and `content-scripts/youtube-bilingual-sidebar.js`. Reference files and bundled
application code remain outside the repository.

| Reference behavior | Veloa implementation |
| --- | --- |
| Toolbar action opens an extension popup | `action.default_popup` opens `popup.html` in both MV3 packages |
| Youtube Dubbing uses a 420px popup with embedded settings | 420px popup with an internal settings iframe and back button; no tab creation |
| YouTube sidebar precedes recommended videos | Prepend to `ytd-watch-flexy #secondary-inner`, then `#secondary` or `#related` fallback |
| Source-first bilingual transcript | Original above translation, 48px timestamp column, click-to-seek |
| Purple/cyan sidebar, rounded shell, active row accent | Matching reference dimensions: 18px corners, 54px header, 3px top gradient and active stripe |
| Full scrollable transcript | Height `min(72vh,760px)`, minimum 380px, virtualized rows to bound DOM size |
| Manual scroll temporarily overrides auto-follow | 2.6-second hold and explicit return-to-video button |
| Sidebar limited to normal desktop watch | Hide below 980px, in theater/fullscreen, and away from `/watch`; use existing overlay |
| YouTube light/dark appearance | Follow the document `dark` attribute within a closed Shadow DOM |

Live YouTube additionally exposed the `fixed-default-panels` layout: its historical
`#secondary-inner` exists but sits in an initially hidden side panel. Veloa reserves a
380px right dock in that layout and constrains the page width so the video remains
uncovered. Opening YouTube's own fixed panel temporarily hides the dock and restores
the original page width. The classic recommendations-column placement is unchanged.
Page-level styles ship as a declared web-accessible CSS resource, rather than inline
style text. The page width cap handles YouTube's competing width rules.

The sidebar preserves the reference's visual language at the user's explicit request.
It is an independent implementation integrated with this project's subtitle state.
The reference's dubbed-video export is not exposed: this project implements SRT export,
not a video recorder. There is no inactive export-video button.

## Brand and hierarchy

Visible name: **Veloa**. Tagline: **Nghe tron. Hieu sau.** (localized with Vietnamese
diacritics in the interface). The graphite icon contains two offset rounded lines,
representing source and translation. SVG is the design source; toolbar PNGs are
supersampled at 16/32/48/128px to avoid jagged edges.

Popup hierarchy: current video, voice/subtitle selection, primary action, audio mixer,
study tools. Advanced translation and BGM controls use progressive disclosure. Settings
stay in the popup, preserving the active video tab. The original service names, addon
ID, IndexedDB namespace and Native Messaging identity remain unchanged.

Apple HIG sources reviewed on 2026-11-03:

- https://developer.apple.com/design/human-interface-guidelines/layout.md
- https://developer.apple.com/design/human-interface-guidelines/motion.md

Applied principles: consistent alignment, grouping by function, important controls first,
progressive disclosure, brief purposeful transitions, optional motion, keyboard focus,
and reduced-motion/contrast preferences. Web CSS approximates the material treatment;
this is not a native Apple UI or certification of HIG compliance.

Chrome Web Store search for Veloa returned no results on 2026-11-03. Mozilla's web
search presented a client challenge; its public API returned fuzzy matches without an
exact name on the inspected first page. These observations do not establish global
name or trademark uniqueness.

## Interaction and regression checks

`tools/ui_acceptance.py` opens the actual Chromium toolbar popup through the action API
and attaches to its CDP target. It verifies active-video routing, embedded settings,
no new browser tabs, continued work after closing, live backend translation, original/
translated row order, volume control, summary navigation, SRT import, and stop.

The YouTube layout is an explicitly labelled local DOM fixture at a routed HTTPS URL;
it is not a claim of testing a live YouTube redesign. The production sidebar class is
also exercised with 5,000 fixture cues, distant seeks and manual scrolling. A measured
height anchor prevents virtualized rows moving the viewport unexpectedly; distant
seeks jump directly, while nearby movement remains animated.

Reports: `research/ui-acceptance.json`, `research/browser-firefox.json`,
`research/ui-youtube-live.json`. `tools/youtube_layout_acceptance.py` separately tests
the real YouTube watch DOM: visible sidebar without covering the video, native side
panel transitions, subtitle mode transitions, and 1000px/800px widths. This layout
check makes no paid provider calls and does not claim a full live YouTube dubbing run.
Private screenshots: `.private/ui-qa/popup.png`, `popup-settings.png`, `popup-mixer.png`,
`youtube-light.png`, `youtube-dark.png`. Test profiles and credentials are ignored.
Firefox's existing live acceptance script checks the actual MV3 background-scripts
package, translation and audio playback. The automated toolbar-popup interaction test
in this revision is Chromium-specific.
