# Multisite routing and coverage

Generated from the statically inspected local reference. The 159 rows include repeated
brands and embedded players. Shared readers work only when the page exposes a supported
caption representation. Registry membership does not mean a bespoke API was ported or
that the live site passed testing. See MULTISITE_ANALYSIS.md for evidence and limits.
Full lesson patterns and selectors: research/multisite-inventory.json.

| Site | Domain pattern | Reference method | Veloa implementation | Live evidence |
| --- | --- | --- | --- | --- |
| youtube | *://*.youtube.com/* | youtube | Dedicated YouTube player/timedtext/transcript | Not individually live verified |
| youtube | *://*.youtube-nocookie.com/* | youtube | Dedicated YouTube player/timedtext/transcript | Not individually live verified |
| google_drive_youtube | *://youtube.googleapis.com/* | google_drive_youtube | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| youtube | *://*.youtube.com/* | youtube | Dedicated YouTube player/timedtext/transcript | Not individually live verified |
| egghead | *://egghead.io/* | egghead | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| thought_industries_wistia | *://*.thoughtindustries.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| thought_industries_wistia | *://learn.getdbt.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| thought_industries_wistia | *://learn.getdbt.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| thought_industries_wistia | *://academy.tricentis.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| thought_industries_wistia | *://learn.educate360.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| ardan_labs_thinkific | *://courses.ardanlabs.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| thinkific_course_player | *://*/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| ahrefs_wistia | *://ahrefs.com/* | wistia | Wistia player identity + inline captions | Live page uses YouTube embed; captions unknown |
| comsol_wistia | *://*.comsol.*/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| rti_wistia | *://www.rti.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| psychwire_wistia | *://psychwire.com/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| kajabi_mobile_wistia_frame | *://fast.wistia.net/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| unrealmasterclass_wistia | *://fast.wistia.net/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| sheridan_wistia | *://fast.wistia.net/* | wistia | Wistia player identity + inline captions | Not individually live verified |
| kajabi_wistia | *://*/* | kajabi | Wistia player identity + inline captions | Not individually live verified |
| unrealmasterclass_top_frame | *://www.unrealmasterclass.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| sheridan_top_frame | *://www.sheridanriskmanagement.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| domestika | *://www.domestika.org/* | domestika | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| mindvalley | *://home.mindvalley.com/* | mindvalley | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| hubspot_video | *://*.hubspotvideo.com/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| zenva | *://academy.zenva.com/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| nma_art | *://www.nma.art/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| datacamp_projector | *://projector.datacamp.com/* | datacamp | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| lecturio | *://app.lecturio.com/* | lecturio | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| platzi | *://platzi.com/* | platzi | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| kollus | *://v.kr.kollus.com/* | kollus | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| dailymotion | *://geo.dailymotion.com/* | dailymotion | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| bbc | *://*.bbc.com/* | bbc | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| bloomberg | *://*.bloomberg.com/* | bloomberg | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| coindesk | *://*.coindesk.com/* | coindesk_jwplayer | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| reuters | *://*.reuters.com/* | reuters_jwplayer | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| streamuj_tv | *://www.streamuj.tv/* | jwplayer | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| kisskh | *://kisskh.do/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| dramawave | *://dramawave.dramafren.org/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| plex | *://watch.plex.tv/* | plex | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| aljazeera | *://*.aljazeera.com/* | aljazeera_brightcove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| oracle_mylearn | *://mylearn.oracle.com/* | oracle_mylearn_brightcove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| sonicwall | *://www.sonicwall.com/support/video-tutorials/* | sonicwall_brightcove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| servicenow | *://learning.servicenow.com/* | servicenow_brightcove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| narto | *://narto-drama.com/detail/watch/* | narto | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| kinescope | *://kinescope.io/* | kinescope | Captured playlist player + VTT tracks | Not individually live verified |
| sketchy_cloudflare | *://customer-uvgt1jgt7nqod9np.cloudflarestream.com/* | sketchy_cloudflare | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| nbcnews | *://*.nbcnews.com/* | jwplayer | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| jwplayer_hosted | *://cdn.jwplayer.com/players/*.html* | jwplayer_hosted | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| jwplayer_hosted | *://content.jwplatform.com/players/*.html* | jwplayer_hosted | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| cbsnews | *://*.cbsnews.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| barrons | *://*.barrons.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| wsj | *://*.wsj.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| aihero | *://www.aihero.dev/* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| maven | *://maven.com/* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| maven | *://maven.com/* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| maven | *://maven.com/* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| mux | *://whop.com/* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| crusherfiremedia_mux | *://www.crusherfiremedia.com/mux-embed* | mux | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| bili | *://*.bilibili.com/* | bili | UGC aid/cid metadata + epInfo + shared/CC fallback; PGC/PUGV APIs incomplete | UGC /en/video sample: native button; anonymous captions require session; other routes unverified |
| bili | *://www.bilibili.com/* | bili | UGC aid/cid metadata + epInfo + shared/CC fallback; PGC/PUGV APIs incomplete | UGC /en/video sample: native button; anonymous captions require session; other routes unverified |
| udemy | *://*.udemy.*/* | udemy | Configured metadata schema + shared subtitle readers | Not individually live verified |
| leadconnector_course | *://*.rapid-flow.shop/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| clientclub | *://*.app.clientclub.net/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| gamedev | *://iframe.mediadelivery.net/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| epicgames | *://dev.epicgames.com/* | videojs | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| coursera | *://*.coursera.org/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| autodesk | *://*.autodesk.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| vimeo | *://player.vimeo.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| vimeo | *://vimeo.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| threejs_journey | *://threejs-journey.com/lessons/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| dropbox | *://*.dropbox.com/* | dropbox | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| illinois | *://mediaspace.illinois.edu/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| esri_kaltura | *://mediaspace.esri.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| brightcove_ | *://players.brightcove.net/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| hotmart | *://*.hotmart.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| deeplearning.ai | *://learn.deeplearning.ai/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| harvard | *://opencast.dcex.harvard.edu/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| zoom_illinois | *://illinois.zoom.us/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| khanacademy | *://*.khanacademy.org/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| edx | *://courses.edx.org/* | edx | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| ucdavis_mobile_kaltura_frame | *://cdnapisec.kaltura.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| kaltura | *://cdnapisec.kaltura.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| ixl | *://www.ixl.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| linkedin_learning | *://www.linkedin.com/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| anthropic_skilljar | *://anthropic.skilljar.com/* | jwplayer | JWPlayer owned playlist tracks + HLS sources | Not individually live verified |
| internet_archive | *://archive.org/* | internet_archive | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| tiktok | *://*.tiktok.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| douyin | *://*.douyin.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| x | *://*.x.com/* | twitter | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| twitter | *://*.twitter.com/* | twitter | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| facebook | *://*.facebook.com/* | facebook | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| codewithmosh_teachable | *://codewithmosh.teachable.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| openai_article | *://openai.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| spotify_episode | *://open.spotify.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| ted | *://*.ted.com/* | ted | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| apple_developer | *://developer.apple.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | 360 cues acquired on one live sample |
| learn_microsoft | *://learn.microsoft.com/* | apiIntercept | Configured metadata schema + shared subtitle readers | Not individually live verified |
| unity_learn | *://learn.unity.com/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| artstation | *://www.artstation.com/* | artstation | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| masterclass | *://*.masterclass.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| jove | *://www.jove.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| frontendmasters | *://frontendmasters.com/* | commonVtt | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| internetfundamentals | *://internetfundamentals.com/* | internetfundamentals | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| feynmanlectures | *://www.feynmanlectures.caltech.edu/* | feynmanlectures | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| rachelsenglish | *://rachelsenglish.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| motionmagic | *://*.themotionmagic.com/* | motionmagic | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| memberspot | *://community.memberspot.de/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| memberspot | *://*.mymemberspot.de/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| pocketstudio | *://pocketstudio.com.tw/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| mathworks | *://www.mathworks.com/* | mathworks_brightcove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| fautv | *://www.fau.tv/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| ucdavis_kaltura | *://video.ucdavis.edu/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| pluralsight | *://app.pluralsight.com/* | pluralsight | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| movebox | *://movebox.run/* | movebox | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| vidlove | *://vidlove.cc/* | vidlove | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| oba | *://oba.gov.tr/* | oba | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| art21 | *://art21.org/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| pendo_wistia | *://www.pendo.io/* | pendo | Wistia player identity + inline captions | Not individually live verified |
| cursor_blog | *://cursor.com/* | cursor_blog | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| oreilly_learning | *://learning.oreilly.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| sap_learning | *://learning.sap.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| updraft | *://updraft.cyfrin.io/* | updraft | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| osmosis | *://www.osmosis.org/* | osmosis | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| medbridge | *://www.medbridge.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| medbridge_course | *://www.medbridge.com/* | medbridge_course | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| patreon | *://www.patreon.com/* | patreon | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| substack | *://*.substack.com/* | substack | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| mightynetworks | *://*.mn.co/* | mightynetworks | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| nebula | *://nebula.tv/* | nebula | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| vkvideo | *://*.vkvideo.ru/* | vkvideo | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| okru | *://ok.ru/video/* | okru | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| navertv | *://tv.naver.com/* | navertv | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| rutube | *://rutube.ru/* | rutube | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| dzen | *://dzen.ru/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| espn | *://*.espn.com/* | commonM3u8 | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| rumble | *://rumble.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| gaia | *://www.gaia.com/video/* | gaia | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| skillshare | *://www.skillshare.com/* | skillshare | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| tella | *://www.tella.tv/video/* | tella | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| skool | *://www.skool.com/*/classroom* | skool | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| loom | *://www.loom.com/embed/* | loom | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| elevify | *://app.elevify.com/slider/* | apiIntercept | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| chartacademy | *://app.chartacademy.com/* | chartacademy | Configured metadata schema + shared subtitle readers | Not individually live verified |
| circle_academy | *://*/* | circle_academy | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| vidtube | *://vidtube.site/* | vidtube | Configured metadata schema + shared subtitle readers | Not individually live verified |
| edusoho-replay | *://live.edusoho.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| qiqiuyun | *://*.qiqiuyun.net/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| vidyard | *://play.vidyard.com/* | vidyard | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| gumlet | *://play.gumlet.io/* | gumlet | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| gitir | *://git.ir/* | gitir | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| ftstreaming | *://ftstreaming.com/* | ftstreaming | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| pandavideo | *://*.tv.pandavideo.com.br/* | pandavideo | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| adobe_tv | *://video.tv.adobe.com/* | adobetv | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| langchain_academy_multimedia_top_frame | *://academy.langchain.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| descript_embed | *://share.descript.com/* | domTrack | Shared DOM/open-shadow/SDK/HLS reader | Not individually live verified |
| odysee | *://*.odysee.com/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| glo | *://www.glo.com/class/* | glo | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
| common | *://*/* | universal | Shared native tracks/HLS only; bespoke API not implemented | Not individually live verified |
