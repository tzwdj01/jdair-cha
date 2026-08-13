(() => {
  "use strict";

  const els = {
    device: document.querySelector("#deviceSelect"),
    start: document.querySelector("#startButton"),
    stopStream: document.querySelector("#stopStreamButton"),
    closeSession: document.querySelector("#closeSessionButton"),
    video: document.querySelector("#video"),
    placeholder: document.querySelector("#videoPlaceholder"),
    featureBadge: document.querySelector("#featureBadge"),
    videoBadge: document.querySelector("#videoBadge"),
    videoTitle: document.querySelector("#videoTitle"),
    firstFrame: document.querySelector("#firstFrameStatus"),
    sessionStatus: document.querySelector("#sessionStatus"),
    connectionStatus: document.querySelector("#connectionStatus"),
    playbackStatus: document.querySelector("#playbackStatus"),
    currentDevice: document.querySelector("#currentDevice"),
    videoMetrics: document.querySelector("#videoMetrics"),
    heartbeatStatus: document.querySelector("#heartbeatStatus"),
    message: document.querySelector("#message"),
  };

  let sessionId = "";
  let streamId = "";
  let client = null;
  let controlSocket = null;
  let heartbeatTimer = null;
  let firstFrameTimer = null;
  let connected = false;
  let connectionError = null;
  let closing = false;

  function apiUrl(path) {
    return path.startsWith("/") ? path : `/api/v2/realtime/${path}`;
  }

  function websocketUrl(path) {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${location.host}${path}`;
  }

  async function api(path, options = {}) {
    const response = await fetch(apiUrl(path), {
      cache: "no-store",
      credentials: "same-origin",
      headers: {"content-type": "application/json", ...(options.headers || {})},
      ...options,
    });
    const payload = await response.json().catch(() => ({
      ok: false,
      data: {code: "invalid_response", message: "服务返回了无效响应。"},
    }));
    if (!response.ok || !payload.ok) {
      const error = new Error(payload?.data?.message || "请求失败。");
      error.code = payload?.data?.code || "request_failed";
      throw error;
    }
    return payload.data;
  }

  function tone(status) {
    if (["PLAYING", "READY", "已连接", "首帧成功"].includes(status)) return "ok";
    if (["FAILED", "连接失败", "播放失败"].includes(status)) return "bad";
    if (["CREATING", "CONNECTING", "WAITING_FIRST_FRAME", "CLOSING"].includes(status)) return "busy";
    return "neutral";
  }

  function badge(element, text) {
    element.textContent = text;
    element.className = `badge ${tone(text)}`;
  }

  function setMessage(text = "") {
    els.message.textContent = text;
  }

  function setSessionStatus(status) {
    els.sessionStatus.textContent = status;
    badge(els.featureBadge, status);
  }

  function setPlaybackStatus(status) {
    els.playbackStatus.textContent = status;
    badge(els.videoBadge, status);
  }

  function showPlaceholder(text, idle = false) {
    els.placeholder.classList.remove("hidden");
    els.placeholder.classList.toggle("idle", idle);
    els.placeholder.querySelector("p").textContent = text;
  }

  function hidePlaceholder() {
    els.placeholder.classList.add("hidden");
  }

  function refreshButtons() {
    const hasStream = Boolean(streamId);
    els.start.disabled = closing || hasStream || !els.device.value;
    els.stopStream.disabled = closing || !hasStream;
    els.closeSession.disabled = closing || !sessionId;
    els.device.disabled = closing || hasStream;
  }

  async function loadDevices() {
    try {
      const data = await api("devices");
      els.device.innerHTML = '<option value="">请选择在线设备</option>';
      for (const device of data.devices) {
        const option = document.createElement("option");
        option.value = device.device_id;
        option.disabled = !device.online;
        option.textContent = `${device.online ? "●" : "○"} ${device.name} · ${device.device_id} · ${device.group}`;
        els.device.appendChild(option);
      }
      setMessage(data.devices.length ? "" : "当前没有可用设备。");
    } catch (error) {
      els.device.innerHTML = '<option value="">设备加载失败</option>';
      setMessage(error.message);
    }
    refreshButtons();
  }

  function sendControl(payload) {
    if (controlSocket?.readyState === WebSocket.OPEN) {
      controlSocket.send(JSON.stringify(payload));
    }
  }

  function sendEvent(event, details = {}, errorCode = "") {
    sendControl({
      type: "event",
      event,
      stream_id: streamId || null,
      error_code: errorCode || null,
      details,
    });
  }

  function waitForControlOpen() {
    return new Promise((resolve, reject) => {
      if (controlSocket?.readyState === WebSocket.OPEN) return resolve();
      const timer = setTimeout(() => reject(new Error("CHA 控制通道连接超时。")), 8000);
      controlSocket.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, {once: true});
      controlSocket.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error("CHA 控制通道连接失败。"));
      }, {once: true});
    });
  }

  function connectControl(path) {
    controlSocket = new WebSocket(websocketUrl(path));
    controlSocket.addEventListener("message", async (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message.type !== "command") return;
      let ok = true;
      let errorCode = "";
      try {
        if (message.action === "close_stream") {
          await releaseSdkStream(message.payload?.device_id || els.device.value);
        } else if (message.action === "close_session") {
          await releaseSdkSession();
        }
      } catch (error) {
        ok = false;
        errorCode = error.code || "CLIENT_RELEASE_FAILED";
      }
      sendControl({
        type: "ack",
        command_id: message.command_id,
        ok,
        error_code: errorCode || null,
      });
    });
    controlSocket.addEventListener("close", () => {
      if (!closing && sessionId) {
        els.connectionStatus.textContent = "控制通道已断开";
        sendEvent("browser_disconnected");
      }
    });
  }

  async function createSession() {
    if (sessionId) return;
    setSessionStatus("CREATING");
    const session = await api("sessions", {
      method: "POST",
      body: JSON.stringify({client_label: "single-viewer"}),
    });
    sessionId = session.session_id;
    setSessionStatus(session.status);
    els.closeSession.disabled = false;
  }

  function gatewaySettings(gatewayPath) {
    return {
      host: location.host,
      port: location.protocol === "https:" ? 443 : 80,
      token: "",
      uid: "cha-realtime",
      pwd: "",
      encryType: "v2",
      encryTime: Math.floor(Date.now() / 1000),
      ssl: location.protocol === "https:",
      privateNet: false,
      httpProxy: gatewayPath,
      localVideo: null,
      localAudio: null,
    };
  }

  function waitForRoom(timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const started = Date.now();
      const timer = setInterval(() => {
        if (connected) {
          clearInterval(timer);
          resolve();
        } else if (connectionError) {
          clearInterval(timer);
          reject(connectionError);
        } else if (Date.now() - started > timeoutMs) {
          clearInterval(timer);
          reject(new Error("加入 mcs8_admin 媒体房间超时。"));
        }
      }, 150);
    });
  }

  function waitForFirstFrame(timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      if (els.video.srcObject && els.video.videoWidth > 0) {
        resolve();
        return;
      }
      const onLoaded = () => {
        clearTimeout(firstFrameTimer);
        resolve();
      };
      els.video.addEventListener("loadeddata", onLoaded, {once: true});
      firstFrameTimer = setTimeout(() => {
        firstFrameTimer = null;
        els.video.removeEventListener("loadeddata", onLoaded);
        const error = new Error("等待首帧超时。");
        error.code = "FIRST_FRAME_TIMEOUT";
        reject(error);
      }, timeoutMs);
    });
  }

  function safeManageEvent(event) {
    const method = event?.method || "";
    const code = Number(event?.errCode || 0);
    if (method === "responseConnectGateway" && code === 200) {
      els.connectionStatus.textContent = "Gateway 已连接";
      sendEvent("gateway_connected");
    } else if (method === "ConnecteInfo") {
      els.connectionStatus.textContent = "媒体服务已解析";
      sendEvent("media_resolved");
    } else if (method === "joinRoom" && code === 200) {
      connected = true;
      els.connectionStatus.textContent = "mcs8_admin 已加入";
      sendEvent("room_joined");
    } else if (method === "newConsumer") {
      els.connectionStatus.textContent = "收到视频轨道";
    } else if (code && code !== 200) {
      els.connectionStatus.textContent = `${method || "AEE"} 失败`;
      const error = new Error(
        method === "responseConnectGateway"
          ? "AEE Gateway 连接失败。"
          : method === "responseConnectMedia"
            ? "AEE 媒体服务连接失败。"
            : method === "joinRoom"
              ? "加入 mcs8_admin 媒体房间失败。"
              : "AEE 实时视频连接失败。"
      );
      error.code = (
        method === "responseConnectGateway"
          ? "GATEWAY_CONNECT_FAILED"
          : method === "responseConnectMedia"
            ? "MEDIA_CONNECT_FAILED"
            : method === "joinRoom"
              ? "ROOM_JOIN_FAILED"
              : "AEE_CONNECT_FAILED"
      );
      connectionError = error;
    }
  }

  async function startPlayback() {
    if (!els.device.value || streamId || closing) return;
    const deviceId = els.device.value;
    setMessage("");
    showPlaceholder("正在建立 CHA 会话…");
    setPlaybackStatus("CONNECTING");
    els.currentDevice.textContent = deviceId;
    els.videoTitle.textContent = `设备 ${deviceId}`;
    els.firstFrame.textContent = "正在建立会话";
    try {
      await createSession();
      const data = await api(`sessions/${sessionId}/streams`, {
        method: "POST",
        body: JSON.stringify({device_id: deviceId}),
      });
      streamId = data.stream.stream_id;
      setSessionStatus(data.session.status);
      if (client && !data.session.connection_reusable) {
        await releaseSdkSession();
      }
      if (!controlSocket || controlSocket.readyState !== WebSocket.OPEN) {
        connectControl(data.connection.control_path);
        await waitForControlOpen();
      }

      if (!client || !connected) {
        if (typeof window.mcs8Client !== "function") {
          throw new Error("AEE SDK 未正确加载。");
        }
        const nextClient = new window.mcs8Client();
        client = nextClient;
        connected = false;
        connectionError = null;
        nextClient.on("OnManage", (event) => {
          if (client === nextClient) safeManageEvent(event);
        });
        els.connectionStatus.textContent = "正在连接 Gateway";
        nextClient.connect(gatewaySettings(data.connection.gateway_path));
        await waitForRoom();
      } else {
        els.connectionStatus.textContent = "复用现有 mcs8_admin 会话";
      }

      setPlaybackStatus("WAITING_FIRST_FRAME");
      els.firstFrame.textContent = "等待首帧";
      showPlaceholder("设备已连接，等待首帧…");
      sendEvent("waiting_first_frame");
      const result = await client.openVideo(deviceId, els.video, "", "");
      if (result !== 200) {
        const error = new Error(`openVideo 返回 ${result}`);
        error.code = "OPEN_VIDEO_REJECTED";
        throw error;
      }
      sendEvent("open_video_accepted");
      await waitForFirstFrame();
      startHeartbeat();
    } catch (error) {
      await playbackFailed(error.code || "PLAYBACK_START_FAILED", error.message);
    }
    refreshButtons();
  }

  async function playbackFailed(code, message) {
    clearTimeout(firstFrameTimer);
    setPlaybackStatus("FAILED");
    els.firstFrame.textContent = "连接失败";
    setMessage(message || "实时视频连接失败。");
    showPlaceholder("视频连接失败", true);
    sendEvent("playback_failed", {}, code);
    try {
      if (sessionId && streamId) {
        await api(`sessions/${sessionId}/streams/${streamId}`, {method: "DELETE"});
      }
    } catch {}
    await releaseSdkStream(els.device.value).catch(() => {});
    streamId = "";
    refreshButtons();
  }

  async function releaseSdkStream(deviceId) {
    clearTimeout(firstFrameTimer);
    firstFrameTimer = null;
    if (client && deviceId) {
      const result = await client.closeVideo(deviceId, "", "");
      if (![200, 404].includes(result)) {
        const error = new Error(`closeVideo 返回 ${result}`);
        error.code = "CLOSE_VIDEO_REJECTED";
        throw error;
      }
    }
    stopVideoTracks();
  }

  async function releaseSdkSession() {
    clearTimeout(firstFrameTimer);
    const closingClient = client;
    client = null;
    connected = false;
    connectionError = null;
    if (closingClient) {
      await closingClient.close();
      closingClient.removeAllListeners?.("OnManage");
    }
    stopVideoTracks();
  }

  function stopVideoTracks() {
    const stream = els.video.srcObject;
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
    }
    els.video.srcObject = null;
  }

  async function stopStream() {
    if (!sessionId || !streamId || closing) return;
    closing = true;
    setPlaybackStatus("CLOSING");
    els.firstFrame.textContent = "正在释放视频资源";
    refreshButtons();
    try {
      await api(`sessions/${sessionId}/streams/${streamId}`, {method: "DELETE"});
      streamId = "";
      setPlaybackStatus("CLOSED");
      setSessionStatus("READY");
      els.connectionStatus.textContent = "会话保留，可再次播放";
      els.firstFrame.textContent = "视频资源已释放";
      els.videoMetrics.textContent = "—";
      showPlaceholder("视频已关闭", true);
      setMessage("closeVideo 已确认，视频资源已释放；CHA session 仍保留。");
    } catch (error) {
      setMessage(error.message);
      setPlaybackStatus("FAILED");
    } finally {
      closing = false;
      refreshButtons();
    }
  }

  async function closeSession() {
    if (!sessionId || closing) return;
    closing = true;
    setSessionStatus("CLOSING");
    setPlaybackStatus(streamId ? "CLOSING" : "CLOSED");
    els.firstFrame.textContent = "正在关闭完整会话";
    refreshButtons();
    try {
      await api(`sessions/${sessionId}`, {method: "DELETE"});
      await releaseSdkSession();
      stopHeartbeat();
      streamId = "";
      sessionId = "";
      setSessionStatus("CLOSED");
      setPlaybackStatus("CLOSED");
      els.connectionStatus.textContent = "WebSocket 已关闭";
      els.firstFrame.textContent = "完整资源已释放";
      els.currentDevice.textContent = "—";
      els.videoMetrics.textContent = "—";
      els.videoTitle.textContent = "请选择设备开始播放";
      showPlaceholder("会话已关闭", true);
      setMessage("consumer、媒体房间、Gateway WebSocket 和 CHA session 已关闭。");
    } catch (error) {
      setMessage(error.message);
      setSessionStatus("FAILED");
    } finally {
      try { controlSocket?.close(); } catch {}
      controlSocket = null;
      closing = false;
      refreshButtons();
    }
  }

  function startHeartbeat() {
    stopHeartbeat();
    els.heartbeatStatus.textContent = "已启动";
    heartbeatTimer = setInterval(async () => {
      if (!sessionId) return;
      try {
        const session = await api(`sessions/${sessionId}/heartbeat`, {method: "POST"});
        els.heartbeatStatus.textContent = new Date(session.last_heartbeat_at).toLocaleTimeString();
        setSessionStatus(session.status);
      } catch (error) {
        els.heartbeatStatus.textContent = "失败";
        setMessage(`CHA 心跳失败：${error.message}`);
      }
    }, 15000);
  }

  function stopHeartbeat() {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = null;
    els.heartbeatStatus.textContent = "未启动";
  }

  els.video.addEventListener("loadeddata", () => {
    if (!streamId || !els.video.videoWidth) return;
    clearTimeout(firstFrameTimer);
    firstFrameTimer = null;
    hidePlaceholder();
    setPlaybackStatus("PLAYING");
    setSessionStatus("PLAYING");
    els.firstFrame.textContent = "首帧成功";
    els.videoMetrics.textContent = `${els.video.videoWidth} × ${els.video.videoHeight}`;
    const track = els.video.srcObject?.getVideoTracks?.()[0];
    sendEvent("first_frame", {
      width: els.video.videoWidth,
      height: els.video.videoHeight,
      track_state: track?.readyState || "live",
    });
  });

  els.video.addEventListener("error", () => {
    if (streamId) playbackFailed("VIDEO_ELEMENT_ERROR", "浏览器视频元素发生错误。");
  });

  els.device.addEventListener("change", refreshButtons);
  els.start.addEventListener("click", startPlayback);
  els.stopStream.addEventListener("click", stopStream);
  els.closeSession.addEventListener("click", closeSession);
  window.addEventListener("pagehide", () => {
    stopHeartbeat();
    try { controlSocket?.close(); } catch {}
    if (client) client.close().catch(() => {});
    stopVideoTracks();
  });

  showPlaceholder("视频未连接", true);
  refreshButtons();
  loadDevices();
})();
