(() => {
  "use strict";

  const state = {
    sessionId: "",
    client: null,
    joined: false,
    connectionError: null,
    devices: [],
    videos: new Map(),
    audios: new Map(),
    streams: new Map(),
    events: [],
    startedAt: performance.now(),
  };

  const grid = document.querySelector("#grid");
  const status = document.querySelector("#state");
  const log = document.querySelector("#log");

  function wsUrl(path) {
    return `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}${path}`;
  }

  function event(name, data = {}) {
    const item = {at_ms: Math.round(performance.now()), event: name, ...data};
    state.events.push(item);
    log.textContent = `${JSON.stringify(item)}\n${log.textContent}`.slice(0, 12000);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      cache: "no-store",
      headers: {"content-type": "application/json"},
      ...options,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function createTiles(devices) {
    grid.innerHTML = "";
    for (const deviceId of devices) {
      const tile = document.createElement("section");
      tile.className = "tile";
      tile.innerHTML = `<strong>${deviceId}</strong><div data-status>idle</div><video autoplay muted playsinline></video><audio autoplay muted></audio>`;
      grid.appendChild(tile);
      const video = tile.querySelector("video");
      const audio = tile.querySelector("audio");
      state.videos.set(deviceId, video);
      state.audios.set(deviceId, audio);
      state.streams.set(deviceId, {
        device_id: deviceId,
        status: "IDLE",
        open_started_at_ms: null,
        first_frame_at_ms: null,
        first_frame_latency_ms: null,
        width: null,
        height: null,
        track_state: null,
        close_result: null,
      });
      video.addEventListener("loadeddata", () => {
        const stream = state.streams.get(deviceId);
        if (!stream || !video.videoWidth) return;
        stream.status = "PLAYING";
        stream.first_frame_at_ms = Math.round(performance.now());
        stream.first_frame_latency_ms =
          stream.first_frame_at_ms - stream.open_started_at_ms;
        stream.width = video.videoWidth;
        stream.height = video.videoHeight;
        stream.track_state =
          video.srcObject?.getVideoTracks?.()[0]?.readyState || null;
        tile.querySelector("[data-status]").textContent = "PLAYING";
        event("first_frame", {
          device_id: deviceId,
          latency_ms: stream.first_frame_latency_ms,
          width: stream.width,
          height: stream.height,
          track_state: stream.track_state,
        });
      });
    }
  }

  function gatewaySettings(path) {
    return {
      host: location.host,
      port: Number(location.port || (location.protocol === "https:" ? 443 : 80)),
      token: "",
      uid: "cha-m32a-probe",
      pwd: "",
      encryType: "v2",
      ssl: location.protocol === "https:",
      privateNet: false,
      httpProxy: path,
      localVideo: null,
      localAudio: null,
    };
  }

  async function waitFor(predicate, timeoutMs, label) {
    const started = performance.now();
    while (performance.now() - started < timeoutMs) {
      if (predicate()) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`${label} timeout`);
  }

  async function initialize() {
    const session = await api("/api/probe/session", {method: "POST", body: "{}"});
    state.sessionId = session.session_id;
    state.devices = session.devices;
    createTiles(state.devices);
    const client = new window.mcs8Client();
    state.client = client;
    client.on("OnManage", (message) => {
      const method = message?.method || "";
      const code = Number(message?.errCode || 0);
      if (method === "joinRoom" && code === 200) {
        state.joined = true;
        status.textContent = "joined mcs8_admin";
      } else if (method === "newConsumer") {
        event("new_consumer", {
          device_id: message?.data?.deviceId || message?.data?.peerId || null,
          consumer_id: message?.data?.id || null,
          producer_id: message?.data?.producerId || null,
          transport_id: message?.data?.appData?.transportId || null,
          kind: message?.data?.kind || null,
          codec: message?.data?.rtpParameters?.codecs?.[0]?.mimeType || null,
        });
      } else if (code && code !== 200) {
        state.connectionError = new Error(`${method || "AEE"} failed ${code}`);
        event("connection_error", {method, code});
      } else if (["responseConnectGateway", "responseConnectMedia", "ConnecteInfo"].includes(method)) {
        event(method, {code});
      }
    });
    client.connect(gatewaySettings(session.gateway_path));
    await waitFor(
      () => state.joined || state.connectionError,
      30000,
      "join room",
    );
    if (state.connectionError) throw state.connectionError;
    return snapshot();
  }

  async function openDevice(deviceId) {
    if (!state.devices.includes(deviceId)) throw new Error("device not approved");
    const video = state.videos.get(deviceId);
    const stream = state.streams.get(deviceId);
    stream.status = "OPENING";
    stream.open_started_at_ms = Math.round(performance.now());
    stream.first_frame_at_ms = null;
    stream.first_frame_latency_ms = null;
    stream.close_result = null;
    video.closest(".tile").querySelector("[data-status]").textContent = "OPENING";
    const result = await state.client.openVideo(deviceId, video, "", "");
    event("open_result", {device_id: deviceId, result});
    if (result !== 200) throw new Error(`openVideo ${deviceId} returned ${result}`);
    await waitFor(
      () => stream.status === "PLAYING",
      20000,
      `first frame ${deviceId}`,
    );
    return {...stream};
  }

  async function closeDevice(deviceId) {
    const video = state.videos.get(deviceId);
    const stream = state.streams.get(deviceId);
    const result = await state.client.closeVideo(deviceId, "", "");
    stream.close_result = result;
    stream.status = "CLOSED";
    const tracks = video.srcObject?.getTracks?.() || [];
    for (const track of tracks) track.stop();
    video.srcObject = null;
    video.closest(".tile").querySelector("[data-status]").textContent = "CLOSED";
    event("close_result", {device_id: deviceId, result});
    return {...stream};
  }

  async function probeAudio(deviceId) {
    if (!state.devices.includes(deviceId)) throw new Error("device not approved");
    const audio = state.audios.get(deviceId);
    const video = state.videos.get(deviceId);
    const result = await state.client.openAudio(deviceId, audio, "", "");
    event("open_audio_result", {device_id: deviceId, result});
    if (result !== 200) throw new Error(`openAudio ${deviceId} returned ${result}`);
    await waitFor(
      () => audio.srcObject?.getAudioTracks?.()[0]?.readyState === "live",
      20000,
      `audio track ${deviceId}`,
    );
    const track = audio.srcObject.getAudioTracks()[0];
    audio.muted = true;
    const muted = audio.muted;
    audio.muted = false;
    await audio.play().catch(() => {});
    const unmuted = !audio.muted;
    audio.muted = true;
    const media = state.client?._mediaClientList?.get?.("mcs8_admin");
    const consumers = media?._consumerList
      ? Array.from(media._consumerList.values())
      : [];
    const consumer = [...consumers].reverse().find(
      (item) => item?.kind === "audio" || item?.track?.kind === "audio",
    );
    const codec = consumer?.rtpParameters?.codecs?.[0]?.mimeType || null;
    const trackStateBeforeClose = track.readyState;
    const closeResult = await state.client.closeAudio(deviceId, "", "");
    for (const item of audio.srcObject?.getTracks?.() || []) item.stop();
    audio.srcObject = null;
    assertVideoLive(video, deviceId);
    event("close_audio_result", {device_id: deviceId, result: closeResult});
    return {
      device_id: deviceId,
      open_result: result,
      close_result: closeResult,
      codec,
      track_state_before_close: trackStateBeforeClose,
      track_state_after_close: track.readyState,
      muted,
      unmuted,
      video_track_state:
        video.srcObject?.getVideoTracks?.()[0]?.readyState || null,
    };
  }

  function assertVideoLive(video, deviceId) {
    const track = video?.srcObject?.getVideoTracks?.()[0];
    if (!track || track.readyState !== "live") {
      throw new Error(`video track ${deviceId} was not live after audio close`);
    }
  }

  function internalSdkMetrics() {
    const media = state.client?._mediaClientList?.get?.("mcs8_admin");
    const consumers = media?._consumerList ? Array.from(media._consumerList.values()) : [];
    return {
      media_client_count: state.client?._mediaClientList?.size ?? null,
      consumer_map_size: media?._consumerList?.size ?? null,
      show_video_map_size: media?._showVideoList?.size ?? null,
      consumer_devices: consumers.map((item) => item?.appData?.devId || null),
      consumer_kinds: consumers.map((item) => item?.kind || item?.track?.kind || null),
      consumer_codecs: consumers.map(
        (item) => item?.rtpParameters?.codecs?.[0]?.mimeType || null,
      ),
      consumer_track_states: consumers.map((item) => item?.track?.readyState || null),
      transport_id: media?._consumerTransport?.id || null,
      transport_state: media?._consumerTransport?.connectionState || null,
    };
  }

  async function serverMetrics() {
    return api(`/api/probe/session/${state.sessionId}`);
  }

  function snapshot() {
    return {
      session_id: state.sessionId,
      joined: state.joined,
      streams: Array.from(state.streams.values()).map((item) => ({...item})),
      sdk: internalSdkMetrics(),
      browser: {
        heap_used_bytes: performance.memory?.usedJSHeapSize ?? null,
        heap_total_bytes: performance.memory?.totalJSHeapSize ?? null,
        hardware_concurrency: navigator.hardwareConcurrency || null,
      },
      events: [...state.events],
    };
  }

  async function closeSession() {
    if (state.client) await state.client.close();
    for (const video of state.videos.values()) {
      for (const track of video.srcObject?.getTracks?.() || []) track.stop();
      video.srcObject = null;
    }
    const metrics = await api(`/api/probe/session/${state.sessionId}`, {
      method: "DELETE",
    });
    state.client = null;
    state.joined = false;
    return {browser: snapshot(), server: metrics};
  }

  window.m32aProbe = {
    initialize,
    openDevice,
    closeDevice,
    probeAudio,
    snapshot,
    serverMetrics,
    closeSession,
  };
  status.textContent = "ready";
})();
