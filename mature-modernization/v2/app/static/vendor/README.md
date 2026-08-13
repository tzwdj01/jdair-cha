# AEE browser SDK provenance

`mcs8Client.js` is the existing AEE browser SDK copied from the locally
validated `web_player` proof of concept used for WXB339 realtime playback.

M3.1 does not reimplement or replace its WebRTC media layer. The only local
compatibility adjustment allows `mediaHttpProxy` to use a CHA same-origin
WebSocket path on HTTP as well as HTTPS. Long-lived AEE credentials and real
Gateway/Media tokens are not embedded in this file.

The SDK is treated as a pinned vendor asset. Any future replacement or patch
must rerun the real-device lifecycle baseline and update this note.
