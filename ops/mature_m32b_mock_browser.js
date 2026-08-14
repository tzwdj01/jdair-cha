(() => {
  "use strict";

  const originalFetch = window.fetch.bind(window);
  const sessions = new Map();
  const openAttempts = new Map();
  let sessionSequence = 0;
  let streamSequence = 0;
  window.__m32bMetrics = {
    socketsCreated: 0,
    socketsActive: 0,
    clientsCreated: 0,
    clientsActive: 0,
    streamsOpened: 0,
    streamsClosed: 0,
    tracksActive: 0,
  };
  HTMLMediaElement.prototype.play = function play() {
    return Promise.resolve();
  };
  CanvasRenderingContext2D.prototype.drawImage = function drawImage() {};

  function fakeTrack(kind) {
    return {
      kind,
      readyState: "live",
      stop() {
        this.readyState = "ended";
      },
    };
  }

  function fakeStream(track) {
    return {
      getTracks: () => [track],
      getVideoTracks: () => track.kind === "video" ? [track] : [],
      getAudioTracks: () => track.kind === "audio" ? [track] : [],
    };
  }

  function response(data, status = 200) {
    return Promise.resolve(new Response(JSON.stringify({
      ok: status >= 200 && status < 300,
      data,
    }), {
      status,
      headers: {"content-type": "application/json"},
    }));
  }

  function sessionPublic(session) {
    const streams = [...session.streams.values()];
    let status = "READY";
    const active = streams.filter((stream) => stream.status !== "CLOSED");
    if (active.some((stream) => ["FAILED", "DEGRADED"].includes(stream.status))) {
      status = "DEGRADED";
    } else if (active.length && active.every((stream) => stream.status === "PLAYING")) {
      status = "PLAYING";
    } else if (active.length) {
      status = "CREATING";
    }
    return {
      session_id: session.id,
      status,
      max_streams: 6,
      audio_enabled: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_heartbeat_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 60000).toISOString(),
      closed_at: session.closed ? new Date().toISOString() : null,
      connection_reusable: true,
      streams,
    };
  }

  class FakeWebSocket extends EventTarget {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor(url) {
      super();
      this.url = url;
      this.readyState = FakeWebSocket.CONNECTING;
      this.pending = new Map();
      this.countedClosed = false;
      window.__m32bMetrics.socketsCreated += 1;
      window.__m32bMetrics.socketsActive += 1;
      window.__m32bControlSocket = this;
      setTimeout(() => {
        this.readyState = FakeWebSocket.OPEN;
        this.dispatchEvent(new Event("open"));
      }, 5);
    }

    send(raw) {
      const payload = JSON.parse(raw);
      if (payload.type === "ack") {
        const resolve = this.pending.get(payload.command_id);
        if (resolve) {
          this.pending.delete(payload.command_id);
          resolve(payload);
        }
      }
    }

    issue(action, payload) {
      const commandId = `cmd-${Date.now()}-${Math.random()}`;
      return new Promise((resolve) => {
        this.pending.set(commandId, resolve);
        this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({
            type: "command",
            command_id: commandId,
            action,
            payload,
          }),
        }));
      });
    }

    close() {
      if (this.readyState === FakeWebSocket.CLOSED) return;
      this.readyState = FakeWebSocket.CLOSED;
      if (!this.countedClosed) {
        this.countedClosed = true;
        window.__m32bMetrics.socketsActive -= 1;
      }
      this.dispatchEvent(new CloseEvent("close"));
    }
  }

  window.WebSocket = FakeWebSocket;

  class FakeMcs8Client {
    constructor() {
      this.handlers = new Map();
      this.streams = new Map();
      this.countedClosed = false;
      window.__m32bMetrics.clientsCreated += 1;
      window.__m32bMetrics.clientsActive += 1;
      window.__m32bClient = this;
    }

    on(name, handler) {
      this.handlers.set(name, handler);
    }

    emit(method, errCode = 0) {
      this.handlers.get("OnManage")?.({method, errCode});
    }

    connect() {
      setTimeout(() => this.emit("responseConnectGateway", 200), 10);
      setTimeout(() => this.emit("ConnecteInfo", 0), 15);
      setTimeout(() => this.emit("responseConnectMedia", 200), 20);
      setTimeout(() => this.emit("joinRoom", 200), 25);
    }

    async openVideo(deviceId, video) {
      const attempt = (openAttempts.get(deviceId) || 0) + 1;
      openAttempts.set(deviceId, attempt);
      // The first WXB342 attempt is deliberately accepted without delivering
      // media. This exercises the product's real 20-second first-frame timeout
      // rather than only an immediate SDK rejection.
      if (
        deviceId === "WXB342"
        && attempt === 1
        && !window.__m32bSkipFirstFrameTimeout
      ) return 200;
      const width = deviceId === "WXB320" ? 1280 : 1920;
      const height = deviceId === "WXB320" ? 720 : 1080;
      const track = fakeTrack("video");
      const stream = fakeStream(track);
      Object.defineProperty(video, "srcObject", {
        configurable: true,
        writable: true,
        value: stream,
      });
      Object.defineProperty(video, "videoWidth", {
        configurable: true,
        value: width,
      });
      Object.defineProperty(video, "videoHeight", {
        configurable: true,
        value: height,
      });
      this.streams.set(deviceId, {stream, video});
      window.__m32bMetrics.streamsOpened += 1;
      window.__m32bMetrics.tracksActive += 1;
      setTimeout(() => video.dispatchEvent(new Event("loadeddata")), 5);
      return 200;
    }

    async closeVideo(deviceId) {
      const record = this.streams.get(deviceId);
      const tracks = record?.stream?.getTracks?.() || [];
      for (const track of tracks) track.stop();
      if (record) {
        window.__m32bMetrics.streamsClosed += 1;
        window.__m32bMetrics.tracksActive -= tracks.length;
      }
      if (record?.video) record.video.srcObject = null;
      this.streams.delete(deviceId);
      return 200;
    }

    async openAudio(deviceId, audio) {
      const record = this.streams.get(deviceId);
      if (!record) return 404;
      const track = fakeTrack("audio");
      const stream = fakeStream(track);
      record.audio = audio;
      record.audioStream = stream;
      Object.defineProperty(audio, "srcObject", {
        configurable: true,
        writable: true,
        value: stream,
      });
      window.__m32bMetrics.tracksActive += 1;
      return 200;
    }

    async closeAudio(deviceId) {
      const record = this.streams.get(deviceId);
      if (!record?.audioStream) return 404;
      const tracks = record.audioStream.getTracks();
      for (const track of tracks) track.stop();
      window.__m32bMetrics.tracksActive -= tracks.length;
      if (record.audio) record.audio.srcObject = null;
      record.audio = null;
      record.audioStream = null;
      return 200;
    }

    async close() {
      for (const deviceId of [...this.streams.keys()]) {
        await this.closeAudio(deviceId);
        await this.closeVideo(deviceId);
      }
      if (!this.countedClosed) {
        this.countedClosed = true;
        window.__m32bMetrics.clientsActive -= 1;
      }
    }

    removeAllListeners() {
      this.handlers.clear();
    }
  }

  window.mcs8Client = FakeMcs8Client;

  window.fetch = async (input, options = {}) => {
    const url = new URL(
      typeof input === "string" ? input : input.url,
      location.href,
    );
    if (!url.pathname.startsWith("/api/v2/realtime")) {
      return originalFetch(input, options);
    }
    const method = (options.method || "GET").toUpperCase();
    if (url.pathname.endsWith("/devices")) {
      return response({devices: [
        {device_id: "WXB320", name: "JDTY02000", group: "维修部", online: true},
        {device_id: "WXB337", name: "JDTY02673", group: "维修部", online: true},
        {device_id: "WXB342", name: "JDTY03099", group: "维修部", online: true},
        {device_id: "WXB345", name: "JDTY03101", group: "维修部", online: true},
        {device_id: "WXB353", name: "JDTY04003", group: "维修部", online: true},
        {device_id: "WXB367", name: "JDTY05017", group: "维修部", online: true},
        {device_id: "WXB301", name: "JDTY01828", group: "维修部", online: false},
      ]});
    }
    if (url.pathname.endsWith("/sessions") && method === "POST") {
      const id = `session-${++sessionSequence}`;
      sessions.set(id, {id, streams: new Map(), closed: false});
      return response(sessionPublic(sessions.get(id)), 201);
    }
    const match = url.pathname.match(
      /\/sessions\/([^/]+)(?:\/streams(?:\/([^/]+))?)?(?:\/(heartbeat|audio))?$/,
    );
    if (!match) return response({code: "not_found"}, 404);
    const session = sessions.get(match[1]);
    if (!session) return response({code: "session_not_found"}, 404);

    if (match[3] === "heartbeat") {
      const snapshot = window.chaRealtimeInspection?.snapshot?.();
      for (const item of snapshot?.streams || []) {
        const stream = session.streams.get(item.stream_id);
        if (stream) {
          stream.status = item.status;
          stream.width = Number(item.resolution?.split("×")[0]) || null;
          stream.height = Number(item.resolution?.split("×")[1]) || null;
          stream.track_state = item.track_state;
        }
      }
      return response(sessionPublic(session));
    }

    if (url.pathname.endsWith("/streams") && method === "POST") {
      const body = JSON.parse(options.body || "{}");
      if ([...session.streams.values()].some(
        (stream) => stream.device_id === body.device_id && stream.status !== "CLOSED",
      )) {
        return response({code: "duplicate_device"}, 409);
      }
      const active = [...session.streams.values()].filter(
        (stream) => stream.status !== "CLOSED",
      );
      if (active.length >= 6) return response({code: "stream_limit_reached"}, 409);
      const stream = {
        stream_id: `stream-${++streamSequence}`,
        device_id: body.device_id,
        kind: "video",
        status: "CONNECTING",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        first_frame_at: null,
        closed_at: null,
        width: null,
        height: null,
        track_state: null,
        error_code: null,
        release_mode: null,
        runtime_state: "AUTHORIZED",
        audio: {
          status: "OFF",
          track_state: null,
          codec: null,
          error_code: null,
        },
      };
      session.streams.set(stream.stream_id, stream);
      return response({
        session: sessionPublic(session),
        stream,
        connection: {
          control_path: `/ws/v2/realtime/${session.id}/control`,
          gateway_path: `/ws/v2/realtime/${session.id}/gateway`,
          runtime_path: "/api/v2/realtime/assets/multistream_runtime.js",
          sdk_path: "/api/v2/realtime/assets/mcs8Client.js",
          uid: "cha-realtime",
          max_streams: 6,
        },
      }, 201);
    }

    if (match[2] && match[3] === "audio" && method === "POST") {
      const stream = session.streams.get(match[2]);
      if (!stream) return response({code: "stream_not_found"}, 404);
      const activeAudio = [...session.streams.values()].find(
        (item) => item.stream_id !== stream.stream_id
          && ["OPENING", "PLAYING"].includes(item.audio?.status),
      );
      if (activeAudio) {
        return response({code: "audio_stream_limit_reached"}, 409);
      }
      stream.audio.status = "OPENING";
      return response(sessionPublic(session));
    }

    if (match[2] && match[3] === "audio" && method === "DELETE") {
      const stream = session.streams.get(match[2]);
      if (!stream) return response({code: "stream_not_found"}, 404);
      if (
        window.__m32bControlSocket?.readyState
        === FakeWebSocket.OPEN
      ) {
        await window.__m32bControlSocket.issue("close_audio", {
          stream_id: stream.stream_id,
          device_id: stream.device_id,
        });
      }
      stream.audio.status = "OFF";
      stream.audio.track_state = null;
      return response(sessionPublic(session));
    }

    if (match[2] && method === "DELETE") {
      const stream = session.streams.get(match[2]);
      if (!stream) return response({code: "stream_not_found"}, 404);
      await window.__m32bControlSocket.issue("close_stream", {
        stream_id: stream.stream_id,
        device_id: stream.device_id,
      });
      stream.status = "CLOSED";
      stream.closed_at = new Date().toISOString();
      return response(sessionPublic(session));
    }

    if (method === "DELETE") {
      if (!session.closed) {
        if (
          window.__m32bControlSocket?.readyState
          === FakeWebSocket.OPEN
        ) {
          await window.__m32bControlSocket.issue("close_session", {
            streams: [...session.streams.values()],
          });
        }
        session.closed = true;
        for (const stream of session.streams.values()) stream.status = "CLOSED";
        sessionStorage.setItem(
          "m32bCleanupCount",
          String(Number(sessionStorage.getItem("m32bCleanupCount") || 0) + 1),
        );
      }
      const result = sessionPublic(session);
      result.status = "CLOSED";
      return response(result);
    }
    return response(sessionPublic(session));
  };
})();
