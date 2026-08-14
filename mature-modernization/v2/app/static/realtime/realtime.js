(() => {
  "use strict";

  const FIRST_FRAME_TIMEOUT_MS = 20000;
  const HEARTBEAT_INTERVAL_MS = 15000;
  const AUTO_RECONNECT_DELAY_MS = 1500;
  const MAX_AUTO_RECONNECT_ATTEMPTS = 1;
  const STATUS_TEXT = {
    CONNECTING: "正在连接",
    WAITING_FIRST_FRAME: "等待首帧",
    PLAYING: "实时播放中",
    DEGRADED: "连接异常",
    FAILED: "连接失败",
    CLOSING: "正在关闭",
    CLOSED: "已关闭",
  };
  const ERROR_TEXT = {
    device_offline: "设备当前离线，暂时无法加入实时监控。",
    device_not_found: "没有找到该设备，请刷新设备列表。",
    stream_limit_reached: "当前最多支持 6 路实时视频。",
    duplicate_device: "该设备已在监控中。",
    first_frame_timeout: "视频连接超时，请重试。",
    FIRST_FRAME_TIMEOUT: "视频连接超时，请重试。",
    upstream_connection_failed: "实时视频服务连接失败。",
    AEE_CONNECT_FAILED: "实时视频服务连接失败。",
    DEVICE_MEDIA_OFFLINE: "设备管理状态在线，但媒体通道当前离线，请检查设备后重试。",
    OPEN_VIDEO_REJECTED: "设备未能建立实时视频，请重试。",
    stream_release_failed: "视频资源关闭未确认，其他画面不受影响。",
    screenshot_failed: "当前画面截图失败，请确认视频正在播放后重试。",
    audio_disabled: "实时接收音频当前未启用。",
    audio_stream_limit_reached: "同一时间只能开启一路设备声音。",
    audio_open_failed: "设备声音接收失败，请重试。",
    AUDIO_OPEN_FAILED: "设备声音接收失败，请重试。",
    audio_release_failed: "设备声音关闭未确认，请结束当前会话。",
    authentication_required: "登录状态已失效，请重新登录。",
    request_failed: "操作失败，请稍后重试。",
  };

  const els = {
    theme: document.querySelector("#themeButton"),
    sessionStatus: document.querySelector("#sessionStatus"),
    onlineCount: document.querySelector("#onlineCount"),
    streamCount: document.querySelector("#streamCount"),
    streamLimit: document.querySelector("#streamLimit"),
    heartbeat: document.querySelector("#heartbeatStatus"),
    reconnect: document.querySelector("#reconnectButton"),
    closeSession: document.querySelector("#closeSessionButton"),
    notice: document.querySelector("#globalNotice"),
    refresh: document.querySelector("#refreshDevicesButton"),
    search: document.querySelector("#deviceSearch"),
    filters: [...document.querySelectorAll("[data-filter]")],
    deviceList: document.querySelector("#deviceList"),
    selectedCount: document.querySelector("#selectedCount"),
    startSelected: document.querySelector("#startSelectedButton"),
    connection: document.querySelector("#connectionStatus"),
    layout: document.querySelector("#layoutStatus"),
    grid: document.querySelector("#videoGrid"),
    empty: document.querySelector("#emptyState"),
    footer: document.querySelector("#footerMessage"),
    audioMode: document.querySelector("#audioModeStatus"),
    tileTemplate: document.querySelector("#videoTileTemplate"),
  };

  const state = {
    devices: [],
    selected: new Set(),
    filter: "online",
    sessionId: "",
    sessionStatus: "READY",
    maxStreams: 6,
    audioSupported: false,
    activeAudioStreamId: "",
    controlSocket: null,
    controlReady: null,
    runtime: null,
    runtimeGatewayPath: "",
    openingStreamId: "",
    tiles: new Map(),
    tilePool: [],
    deviceToStream: new Map(),
    heartbeatTimer: null,
    closingSession: false,
    reconnecting: false,
    autoReconnectAttempts: 0,
    autoReconnectTimer: null,
    pageLeaving: false,
  };

  function apiPath(path) {
    return path.startsWith("/") ? path : `/api/v2/realtime/${path}`;
  }

  function wsPath(path) {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${location.host}${path}`;
  }

  async function api(path, options = {}) {
    const response = await fetch(apiPath(path), {
      cache: "no-store",
      credentials: "same-origin",
      headers: {"content-type": "application/json", ...(options.headers || {})},
      ...options,
    });
    const payload = await response.json().catch(() => ({
      ok: false,
      data: {code: "request_failed", message: "服务返回了无效响应。"},
    }));
    if (!response.ok || !payload.ok) {
      const error = new Error(
        ERROR_TEXT[payload?.data?.code]
        || payload?.data?.message
        || "操作失败，请稍后重试。",
      );
      error.code = payload?.data?.code || "request_failed";
      throw error;
    }
    return payload.data;
  }

  function showNotice(message = "", tone = "warning") {
    els.notice.textContent = message;
    els.notice.className = `notice${message ? " show" : ""}${tone ? ` ${tone}` : ""}`;
  }

  function friendlyError(error) {
    return ERROR_TEXT[error?.code] || error?.message || ERROR_TEXT.request_failed;
  }

  function setSessionStatus(status) {
    state.sessionStatus = status || "READY";
    const display = state.sessionId
      ? state.sessionStatus
      : "未开始";
    els.sessionStatus.textContent = display;
    els.sessionStatus.dataset.tone = (
      ["PLAYING", "READY"].includes(state.sessionStatus)
        ? "ok"
        : ["DEGRADED", "FAILED"].includes(state.sessionStatus)
          ? "bad"
          : ["CREATING", "CLOSING"].includes(state.sessionStatus)
            ? "busy"
            : "neutral"
    );
  }

  function activeTileCount() {
    return state.tiles.size;
  }

  function playingCount() {
    return [...state.tiles.values()].filter(
      (record) => record.status === "PLAYING",
    ).length;
  }

  function aggregateSessionStatus() {
    const records = [...state.tiles.values()];
    if (!state.sessionId) return "READY";
    if (!records.length) return "READY";
    if (records.some((item) => ["FAILED", "DEGRADED"].includes(item.status))) {
      return "DEGRADED";
    }
    if (records.every((item) => item.status === "PLAYING")) return "PLAYING";
    if (records.some((item) => item.status === "CLOSING")) return "CLOSING";
    return "CREATING";
  }

  function updateSummary() {
    els.streamCount.textContent = String(activeTileCount());
    els.streamLimit.textContent = String(state.maxStreams);
    els.selectedCount.textContent = String(state.selected.size);
    els.closeSession.disabled = !state.sessionId || state.closingSession;
    const remaining = Math.max(0, state.maxStreams - activeTileCount());
    els.startSelected.disabled = (
      !state.selected.size
      || !remaining
      || state.closingSession
    );
    const activeCount = activeTileCount();
    els.layout.textContent = activeCount <= 1
      ? "单画面"
      : activeCount <= 4
        ? "2 × 2 四画面"
        : "3 × 2 六画面";
    els.footer.textContent = (
      activeTileCount()
        ? `${playingCount()} 路播放中 · ${activeTileCount()} 路已加入`
        : "等待选择设备"
    );
    els.audioMode.innerHTML = state.activeAudioStreamId
      ? '<i class="status-dot ok"></i> 单路接收音频已开启'
      : `<i class="status-dot"></i> ${
        state.audioSupported ? "音频默认关闭" : "音频功能关闭"
      }`;
    if (state.sessionId && !state.closingSession) {
      setSessionStatus(aggregateSessionStatus());
    } else if (!state.sessionId) {
      setSessionStatus("READY");
    }
    updateLayout();
  }

  function updateLayout() {
    const count = activeTileCount();
    els.grid.classList.toggle("empty", count === 0);
    els.grid.classList.toggle("single", count === 1);
    els.grid.classList.toggle("quad", count >= 2 && count <= 4);
    els.grid.classList.toggle("six", count >= 5);
    els.empty.classList.toggle("hidden", count > 0);
  }

  function deviceRuntimeStatus(deviceId) {
    const streamId = state.deviceToStream.get(deviceId);
    return streamId ? state.tiles.get(streamId)?.status || "" : "";
  }

  function renderDevices() {
    const query = els.search.value.trim().toLowerCase();
    const rows = state.devices.filter((device) => {
      if (state.filter === "online" && !device.online) return false;
      const haystack = `${device.device_id} ${device.name} ${device.group}`.toLowerCase();
      return !query || haystack.includes(query);
    });
    els.deviceList.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "device-empty";
      empty.textContent = "没有符合条件的设备";
      els.deviceList.appendChild(empty);
      return;
    }

    const atLimit = activeTileCount() >= state.maxStreams;
    for (const device of rows) {
      const runtimeStatus = deviceRuntimeStatus(device.device_id);
      const selected = state.selected.has(device.device_id);
      const row = document.createElement("label");
      row.className = [
        "device-row",
        device.online ? "" : "offline",
        selected ? "selected" : "",
      ].filter(Boolean).join(" ");
      row.dataset.deviceId = device.device_id;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = selected;
      checkbox.disabled = (
        !device.online
        || Boolean(runtimeStatus)
        || (atLimit && !selected)
      );
      checkbox.addEventListener("change", () => {
        toggleSelection(device.device_id, checkbox.checked);
      });

      const main = document.createElement("span");
      main.className = "device-main";
      const title = document.createElement("strong");
      title.textContent = device.device_id;
      const subtitle = document.createElement("small");
      subtitle.textContent = `${device.name || device.device_id} · ${device.group || "未分组"}`;
      main.append(title, subtitle);

      const actionWrap = document.createElement("span");
      const status = document.createElement("span");
      const statusClass = runtimeStatus
        ? runtimeStatus.toLowerCase()
        : device.online ? "online" : "offline";
      status.className = `device-state ${statusClass}`;
      status.textContent = runtimeStatus
        ? STATUS_TEXT[runtimeStatus] || runtimeStatus
        : device.online ? "在线" : "离线";
      actionWrap.appendChild(status);

      if (device.online && !runtimeStatus) {
        const add = document.createElement("button");
        add.type = "button";
        add.className = "device-add";
        add.textContent = "+";
        add.title = "立即加入监控";
        add.disabled = atLimit || state.closingSession;
        add.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          addDevice(device.device_id);
        });
        actionWrap.appendChild(add);
      }
      row.append(checkbox, main, actionWrap);
      els.deviceList.appendChild(row);
    }
  }

  function toggleSelection(deviceId, selected) {
    if (selected) {
      const remaining = state.maxStreams - activeTileCount();
      if (state.selected.size >= remaining) {
        showNotice(`当前最多支持 ${state.maxStreams} 路实时视频。`);
        renderDevices();
        return;
      }
      state.selected.add(deviceId);
    } else {
      state.selected.delete(deviceId);
    }
    updateSummary();
    renderDevices();
  }

  async function loadDevices({quiet = false} = {}) {
    if (!quiet) els.deviceList.innerHTML = '<div class="device-loading">正在加载设备…</div>';
    try {
      const data = await api("devices");
      state.devices = data.devices || [];
      els.onlineCount.textContent = String(
        state.devices.filter((item) => item.online).length,
      );
      renderDevices();
      if (!quiet) showNotice("");
    } catch (error) {
      els.deviceList.innerHTML = '<div class="device-empty">设备列表加载失败</div>';
      showNotice(friendlyError(error), "error");
    }
  }

  async function createSession() {
    if (state.sessionId) return;
    if (!state.reconnecting) state.autoReconnectAttempts = 0;
    setSessionStatus("CREATING");
    els.connection.textContent = "正在创建 CHA 实时会话";
    const session = await api("sessions", {
      method: "POST",
      body: JSON.stringify({client_label: "six-grid-inspection"}),
    });
    state.sessionId = session.session_id;
    state.maxStreams = Math.min(Number(session.max_streams || 6), 6);
    state.audioSupported = Boolean(session.audio_enabled);
    setSessionStatus(session.status);
    startHeartbeat();
    updateSummary();
  }

  function sendControl(payload) {
    if (state.controlSocket?.readyState === WebSocket.OPEN) {
      state.controlSocket.send(JSON.stringify(payload));
    }
  }

  function sendEvent(event, streamId = null, details = {}, errorCode = null) {
    sendControl({
      type: "event",
      event,
      stream_id: streamId,
      error_code: errorCode,
      details,
    });
  }

  async function ensureControl(path) {
    if (state.controlSocket?.readyState === WebSocket.OPEN) return;
    if (state.controlReady) return state.controlReady;
    state.controlReady = new Promise((resolve, reject) => {
      const socket = new WebSocket(wsPath(path));
      state.controlSocket = socket;
      const timer = setTimeout(() => {
        reject(Object.assign(new Error("控制通道连接超时。"), {
          code: "upstream_connection_failed",
        }));
      }, 8000);
      socket.addEventListener("open", () => {
        clearTimeout(timer);
        els.connection.textContent = "CHA 控制通道已连接";
        resolve();
      }, {once: true});
      socket.addEventListener("error", () => {
        clearTimeout(timer);
        reject(Object.assign(new Error("控制通道连接失败。"), {
          code: "upstream_connection_failed",
        }));
      }, {once: true});
      socket.addEventListener("message", handleControlMessage);
      socket.addEventListener("close", () => {
        if (!state.pageLeaving && !state.closingSession && state.sessionId) {
          markSharedConnectionAbnormal("控制连接已断开，请重新建立监控。");
        }
      });
    }).finally(() => {
      state.controlReady = null;
    });
    return state.controlReady;
  }

  async function handleControlMessage(event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.type !== "command") return;
    let ok = true;
    let errorCode = null;
    try {
      if (!state.runtime) {
        if (message.action !== "close_session") {
          throw Object.assign(new Error("视频运行时不存在。"), {
            code: "CLIENT_RUNTIME_MISSING",
          });
        }
      } else {
        await state.runtime.handleControlCommand(message);
      }
    } catch (error) {
      ok = false;
      errorCode = error.code || "CLIENT_RELEASE_FAILED";
    }
    sendControl({
      type: "ack",
      command_id: message.command_id,
      ok,
      error_code: errorCode,
    });
  }

  function ensureRuntime(connection) {
    if (state.runtime) {
      state.runtime.configure({gatewayPath: connection.gateway_path});
      return state.runtime;
    }
    state.runtimeGatewayPath = connection.gateway_path;
    state.runtime = new window.ChaRealtimeMultiStreamRuntime({
      gatewayPath: connection.gateway_path,
      onEvent: handleRuntimeEvent,
    });
    return state.runtime;
  }

  function handleRuntimeEvent(event) {
    if (event.event === "aee_manage") {
      if (event.method === "responseConnectGateway" && event.code === 200) {
        els.connection.textContent = "AEE Gateway 已连接";
        sendEvent("gateway_connected", state.openingStreamId || null);
      } else if (event.method === "ConnecteInfo") {
        els.connection.textContent = "媒体服务已解析";
        sendEvent("media_resolved", state.openingStreamId || null);
      } else if (event.method === "responseConnectMedia" && event.code === 200) {
        els.connection.textContent = "AEE Media 已连接";
      } else if (event.method === "joinRoom" && event.code === 200) {
        els.connection.textContent = "mcs8_admin 已加入";
        sendEvent("room_joined", state.openingStreamId || null);
      } else if (event.code && event.code !== 200) {
        markSharedConnectionAbnormal("实时视频连接异常，请重新建立监控。");
      }
      return;
    }
    const record = state.tiles.get(event.stream_id);
    if (!record) return;
    if (event.event === "open_video_accepted") {
      if (record.status !== "PLAYING") {
        updateTile(record, "WAITING_FIRST_FRAME", {
          overlayTitle: "等待视频首帧",
          overlayDetail: "设备已连接，正在等待实时画面…",
        });
      }
      sendEvent("open_video_accepted", record.streamId);
    } else if (event.event === "first_frame") {
      clearTimeout(record.firstFrameTimer);
      record.firstFrameTimer = null;
      record.firstFrameAt = Date.now();
      record.resolution = `${event.width} × ${event.height}`;
      record.trackState = event.track_state || "live";
      updateTile(record, "PLAYING");
      sendEvent("first_frame", record.streamId, {
        width: event.width,
        height: event.height,
        track_state: record.trackState,
      });
      showNotice(`${record.deviceId} 已开始实时播放。`, "success");
    } else if (event.event === "audio_playing") {
      record.audioStatus = "PLAYING";
      state.activeAudioStreamId = record.streamId;
      updateTile(record, record.status);
      sendEvent("audio_playing", record.streamId, {
        track_state: event.track_state || "live",
        codec: event.codec || null,
      });
    } else if (event.event === "audio_closed") {
      record.audioStatus = "OFF";
      if (state.activeAudioStreamId === record.streamId) {
        state.activeAudioStreamId = "";
      }
      updateTile(record, record.status);
    }
  }

  function createTile(stream, device) {
    let element = state.tilePool.pop();
    if (!element) {
      const fragment = els.tileTemplate.content.cloneNode(true);
      element = fragment.querySelector(".video-tile");
    }
    const video = element.querySelector("video");
    const audio = element.querySelector("audio");
    const audioButton = element.querySelector('[data-action="audio"]');
    const record = {
      streamId: stream.stream_id,
      deviceId: stream.device_id,
      deviceName: device?.name || stream.device_id,
      element,
      video,
      audio,
      audioButton,
      audioStatus: "OFF",
      status: "CONNECTING",
      errorCode: null,
      firstFrameAt: null,
      firstFrameTimer: null,
      resolution: "—",
      trackState: "—",
    };
    element.dataset.streamId = record.streamId;
    element.classList.remove("hidden");
    element.querySelector("[data-device-id]").textContent = record.deviceId;
    element.querySelector("[data-device-name]").textContent = record.deviceName;
    if (!element.dataset.actionsBound) {
      element.querySelector('[data-action="close"]').addEventListener("click", () => {
        closeTile(element.dataset.streamId);
      });
      element.querySelector('[data-action="retry"]').addEventListener("click", () => {
        retryTile(element.dataset.streamId);
      });
      element.querySelector('[data-action="screenshot"]').addEventListener("click", () => {
        captureFrame(element.dataset.streamId);
      });
      audioButton.addEventListener("click", () => {
        toggleAudio(element.dataset.streamId);
      });
      element.querySelector('[data-action="fullscreen"]').addEventListener("click", () => {
        if (document.fullscreenElement === element) {
          document.exitFullscreen().catch(() => {});
        } else {
          element.requestFullscreen().catch(() => {
            showNotice("浏览器未允许进入全屏。", "error");
          });
        }
      });
      element.dataset.actionsBound = "true";
    }
    audioButton.classList.toggle("hidden", !state.audioSupported);
    state.tiles.set(record.streamId, record);
    state.deviceToStream.set(record.deviceId, record.streamId);
    els.grid.appendChild(element);
    updateTile(record, "CONNECTING");
    updateSummary();
    renderDevices();
    return record;
  }

  function updateTile(record, status, options = {}) {
    record.status = status;
    if (options.errorCode !== undefined) record.errorCode = options.errorCode;
    record.element.dataset.status = status;
    record.element.querySelector("[data-status-label]").textContent = (
      STATUS_TEXT[status] || status
    );
    record.element.querySelector("[data-resolution]").textContent = record.resolution;
    record.element.querySelector("[data-track]").textContent = record.trackState;
    record.element.querySelector("[data-first-frame]").textContent = (
      record.firstFrameAt
        ? new Date(record.firstFrameAt).toLocaleTimeString()
        : status === "FAILED" ? "失败" : "等待中"
    );
    record.audioButton.disabled = status !== "PLAYING";
    record.audioButton.classList.toggle(
      "active",
      record.audioStatus === "PLAYING",
    );
    record.audioButton.textContent =
      record.audioStatus === "PLAYING" ? "🔊" : "🔇";
    const overlay = record.element.querySelector(".tile-overlay");
    const retry = record.element.querySelector('[data-action="retry"]');
    const playing = status === "PLAYING";
    overlay.classList.toggle("hidden", playing);
    retry.classList.toggle(
      "hidden",
      !["FAILED", "DEGRADED"].includes(status),
    );
    overlay.querySelector("[data-overlay-title]").textContent = (
      options.overlayTitle
      || (
        status === "FAILED" ? "视频连接失败"
          : status === "DEGRADED" ? "连接异常"
            : status === "CLOSING" ? "正在关闭视频"
              : status === "WAITING_FIRST_FRAME" ? "等待视频首帧"
                : "正在建立实时连接"
      )
    );
    overlay.querySelector("[data-overlay-detail]").textContent = (
      options.overlayDetail
      || (
        status === "FAILED"
          ? friendlyError({code: record.errorCode})
          : status === "DEGRADED"
            ? "共享连接已断开，请重新建立监控。"
            : status === "CLOSING"
              ? "正在确认 AEE 视频资源释放…"
              : "正在创建视频资源…"
      )
    );
    updateSummary();
    renderDevices();
  }

  function removeTile(streamId) {
    const record = state.tiles.get(streamId);
    if (!record) return;
    clearTimeout(record.firstFrameTimer);
    state.tiles.delete(streamId);
    state.deviceToStream.delete(record.deviceId);
    state.selected.delete(record.deviceId);
    if (state.activeAudioStreamId === streamId) {
      state.activeAudioStreamId = "";
    }
    recycleTile(record);
    updateSummary();
    renderDevices();
  }

  function recycleTile(record) {
    record.video.pause?.();
    record.audio.pause?.();
    record.video.srcObject = null;
    record.audio.srcObject = null;
    record.element.dataset.streamId = "";
    record.element.dataset.status = "CLOSED";
    record.element.classList.add("hidden");
    record.audioButton.classList.remove("active");
    record.audioButton.textContent = "🔇";
    if (!state.tilePool.includes(record.element)) {
      state.tilePool.push(record.element);
    }
  }

  async function addDevice(deviceId) {
    const device = state.devices.find((item) => item.device_id === deviceId);
    if (!device) {
      showNotice(ERROR_TEXT.device_not_found, "error");
      return;
    }
    if (!device.online) {
      showNotice(ERROR_TEXT.device_offline, "error");
      return;
    }
    if (state.deviceToStream.has(deviceId)) {
      showNotice(ERROR_TEXT.duplicate_device, "error");
      return;
    }
    if (activeTileCount() >= state.maxStreams) {
      showNotice(ERROR_TEXT.stream_limit_reached, "error");
      return;
    }
    try {
      await createSession();
      const data = await api(`sessions/${state.sessionId}/streams`, {
        method: "POST",
        body: JSON.stringify({device_id: deviceId}),
      });
      state.maxStreams = Math.min(Number(data.connection.max_streams || 6), 6);
      const record = createTile(data.stream, device);
      state.selected.delete(deviceId);
      await ensureControl(data.connection.control_path);
      const runtime = ensureRuntime(data.connection);
      state.openingStreamId = record.streamId;
      sendEvent("waiting_first_frame", record.streamId);
      record.firstFrameTimer = setTimeout(() => {
        if (record.status === "PLAYING") return;
        record.errorCode = "first_frame_timeout";
        runtime.markFailed(record.streamId);
        updateTile(record, "FAILED", {
          overlayTitle: "视频连接超时",
          overlayDetail: ERROR_TEXT.first_frame_timeout,
        });
        sendEvent(
          "playback_failed",
          record.streamId,
          {},
          "FIRST_FRAME_TIMEOUT",
        );
      }, FIRST_FRAME_TIMEOUT_MS);
      await runtime.openStream({
        streamId: record.streamId,
        deviceId: record.deviceId,
        videoElement: record.video,
        audioElement: record.audio,
      });
      if (record.status !== "PLAYING") {
        updateTile(record, "WAITING_FIRST_FRAME");
      }
      els.connection.textContent = "AEE 实时链路已建立";
    } catch (error) {
      const streamId = state.deviceToStream.get(deviceId);
      const record = streamId ? state.tiles.get(streamId) : null;
      if (record) {
        clearTimeout(record.firstFrameTimer);
        record.errorCode = error.code || "upstream_connection_failed";
        state.runtime?.markFailed(record.streamId);
        updateTile(record, "FAILED", {
          overlayTitle: "视频连接失败",
          overlayDetail: friendlyError(error),
        });
        sendEvent(
          "playback_failed",
          record.streamId,
          {},
          record.errorCode,
        );
      }
      showNotice(friendlyError(error), "error");
    } finally {
      state.openingStreamId = "";
      updateSummary();
      renderDevices();
    }
  }

  async function startSelected() {
    const capacity = state.maxStreams - activeTileCount();
    const targets = [...state.selected].slice(0, capacity);
    if (!targets.length) return;
    els.startSelected.disabled = true;
    for (const deviceId of targets) {
      await addDevice(deviceId);
    }
  }

  async function closeTile(streamId) {
    const record = state.tiles.get(streamId);
    if (!record || record.status === "CLOSING") return false;
    updateTile(record, "CLOSING");
    try {
      const session = await api(
        `sessions/${state.sessionId}/streams/${streamId}`,
        {method: "DELETE"},
      );
      removeTile(streamId);
      reconcileSession(session);
      showNotice(`${record.deviceId} 已关闭，可重新加入监控。`, "success");
      return true;
    } catch (error) {
      record.errorCode = error.code || "stream_release_failed";
      updateTile(record, "FAILED", {
        overlayTitle: "视频关闭未确认",
        overlayDetail: friendlyError(error),
      });
      showNotice(friendlyError(error), "error");
      return false;
    }
  }

  async function retryTile(streamId) {
    const record = state.tiles.get(streamId);
    if (!record || !["FAILED", "DEGRADED"].includes(record.status)) return;
    const deviceId = record.deviceId;
    showNotice(`正在重新连接 ${deviceId}…`);
    const closed = await closeTile(streamId);
    if (closed) await addDevice(deviceId);
  }

  async function toggleAudio(streamId, forceOff = false) {
    const record = state.tiles.get(streamId);
    if (!record || !state.audioSupported || record.status !== "PLAYING") {
      showNotice(ERROR_TEXT.audio_disabled, "error");
      return false;
    }
    const shouldClose = forceOff || record.audioStatus === "PLAYING";
    if (shouldClose) {
      try {
        record.audioStatus = "CLOSING";
        updateTile(record, record.status);
        const session = await api(
          `sessions/${state.sessionId}/streams/${streamId}/audio`,
          {method: "DELETE"},
        );
        record.audioStatus = "OFF";
        if (state.activeAudioStreamId === streamId) {
          state.activeAudioStreamId = "";
        }
        reconcileSession(session);
        updateTile(record, record.status);
        showNotice(`${record.deviceId} 设备声音已关闭。`, "success");
        return true;
      } catch (error) {
        record.audioStatus = "FAILED";
        updateTile(record, record.status);
        showNotice(friendlyError(error), "error");
        return false;
      }
    }
    if (
      state.activeAudioStreamId
      && state.activeAudioStreamId !== streamId
    ) {
      const previousClosed = await toggleAudio(
        state.activeAudioStreamId,
        true,
      );
      if (!previousClosed) return false;
    }
    try {
      await api(
        `sessions/${state.sessionId}/streams/${streamId}/audio`,
        {method: "POST", body: "{}"},
      );
      record.audioStatus = "OPENING";
      updateTile(record, record.status);
      await state.runtime.openAudio(streamId);
      record.audioStatus = "PLAYING";
      state.activeAudioStreamId = streamId;
      updateTile(record, record.status);
      showNotice(`${record.deviceId} 设备声音已开启。`, "success");
      return true;
    } catch (error) {
      record.audioStatus = "FAILED";
      sendEvent(
        "audio_failed",
        streamId,
        {},
        error.code || "AUDIO_OPEN_FAILED",
      );
      await api(
        `sessions/${state.sessionId}/streams/${streamId}/audio`,
        {method: "DELETE"},
      ).catch(() => {});
      updateTile(record, record.status);
      showNotice(friendlyError(error), "error");
      return false;
    }
  }

  function reconcileSession(session) {
    if (!session) return;
    setSessionStatus(session.status);
    state.maxStreams = Math.min(Number(session.max_streams || state.maxStreams), 6);
    for (const stream of session.streams || []) {
      const record = state.tiles.get(stream.stream_id);
      if (!record || stream.status === "CLOSED") continue;
      if (
        ["FAILED", "DEGRADED"].includes(stream.status)
        && record.status !== stream.status
      ) {
        record.errorCode = stream.error_code || stream.status.toLowerCase();
        updateTile(record, stream.status);
      }
      if (stream.audio) {
        record.audioStatus = stream.audio.status || "OFF";
        if (record.audioStatus === "PLAYING") {
          state.activeAudioStreamId = record.streamId;
        } else if (state.activeAudioStreamId === record.streamId) {
          state.activeAudioStreamId = "";
        }
        updateTile(record, record.status);
      }
    }
    const active = (session.streams || []).filter(
      (stream) => stream.status !== "CLOSED",
    );
    if (
      session.status === "DEGRADED"
      && active.length
      && active.every((stream) => stream.status === "DEGRADED")
    ) {
      els.reconnect.classList.remove("hidden");
    }
    updateSummary();
  }

  function markSharedConnectionAbnormal(message) {
    els.connection.textContent = "连接异常";
    els.reconnect.classList.remove("hidden");
    showNotice(message, "error");
    for (const record of state.tiles.values()) {
      if (!["CLOSING", "CLOSED"].includes(record.status)) {
        record.errorCode = "upstream_connection_failed";
        updateTile(record, "DEGRADED");
      }
    }
    state.runtime?.close().catch(() => {});
    state.runtime = null;
    state.runtimeGatewayPath = "";
    setSessionStatus("DEGRADED");
    if (
      state.autoReconnectAttempts < MAX_AUTO_RECONNECT_ATTEMPTS
      && !state.autoReconnectTimer
      && !state.reconnecting
    ) {
      state.autoReconnectAttempts += 1;
      showNotice(
        `${message} 系统将在 ${AUTO_RECONNECT_DELAY_MS / 1000} 秒后尝试一次自动恢复。`,
        "error",
      );
      state.autoReconnectTimer = setTimeout(() => {
        state.autoReconnectTimer = null;
        reconnectSession({automatic: true});
      }, AUTO_RECONNECT_DELAY_MS);
    }
  }

  async function closeSession({quiet = false} = {}) {
    if (!state.sessionId || state.closingSession) return;
    state.closingSession = true;
    setSessionStatus("CLOSING");
    for (const record of state.tiles.values()) {
      if (record.status !== "CLOSED") updateTile(record, "CLOSING");
    }
    try {
      const session = await api(`sessions/${state.sessionId}`, {
        method: "DELETE",
      });
      await state.runtime?.close().catch(() => {});
      resetPage();
      if (!quiet) showNotice("实时监控会话已结束，所有视频资源已释放。", "success");
      return session;
    } catch (error) {
      showNotice(friendlyError(error), "error");
      for (const record of state.tiles.values()) {
        record.errorCode = error.code || "stream_release_failed";
        updateTile(record, "FAILED");
      }
      return null;
    } finally {
      state.closingSession = false;
      updateSummary();
    }
  }

  function resetPage() {
    stopHeartbeat();
    if (state.autoReconnectTimer) clearTimeout(state.autoReconnectTimer);
    state.autoReconnectTimer = null;
    try {
      state.controlSocket?.close();
    } catch {}
    state.controlSocket = null;
    state.controlReady = null;
    state.runtime = null;
    state.runtimeGatewayPath = "";
    for (const record of state.tiles.values()) {
      clearTimeout(record.firstFrameTimer);
      recycleTile(record);
    }
    state.tiles.clear();
    state.deviceToStream.clear();
    state.selected.clear();
    state.sessionId = "";
    state.sessionStatus = "READY";
    state.openingStreamId = "";
    state.activeAudioStreamId = "";
    state.audioSupported = false;
    els.connection.textContent = "尚未建立实时连接";
    els.reconnect.classList.add("hidden");
    els.heartbeat.textContent = "未启动";
    updateSummary();
    renderDevices();
  }

  async function reconnectSession({automatic = false} = {}) {
    if (state.reconnecting) return false;
    state.reconnecting = true;
    els.reconnect.disabled = true;
    const devices = [...state.tiles.values()].map((record) => record.deviceId);
    try {
      const closed = await closeSession({quiet: true});
      if (!closed) throw new Error("The previous realtime session did not close.");
      for (const deviceId of devices.slice(0, state.maxStreams)) {
        await addDevice(deviceId);
      }
      const deadline = Date.now() + FIRST_FRAME_TIMEOUT_MS;
      while (playingCount() !== devices.length && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      if (playingCount() !== devices.length) {
        throw new Error("Not all realtime streams recovered.");
      }
      state.autoReconnectAttempts = 0;
      showNotice("实时监控连接已重新建立。", "success");
      els.reconnect.classList.add("hidden");
      return true;
    } catch (error) {
      els.reconnect.classList.remove("hidden");
      showNotice(
        automatic
          ? "自动恢复未成功，请点击“重新建立监控”手动重试。"
          : friendlyError(error),
        "error",
      );
      return false;
    } finally {
      state.reconnecting = false;
      els.reconnect.disabled = false;
    }
  }

  function safeFilename(value) {
    return String(value || "device").replace(/[^A-Za-z0-9_.-]+/g, "_");
  }

  async function captureFrame(streamId) {
    const record = state.tiles.get(streamId);
    if (
      !record
      || record.status !== "PLAYING"
      || !record.video.videoWidth
      || !record.video.videoHeight
    ) {
      showNotice(ERROR_TEXT.screenshot_failed, "error");
      sendEvent("screenshot_failed", streamId, {}, "SCREENSHOT_NOT_READY");
      return false;
    }
    try {
      const canvas = document.createElement("canvas");
      canvas.width = record.video.videoWidth;
      canvas.height = record.video.videoHeight;
      const context = canvas.getContext("2d", {alpha: false});
      if (!context) throw new Error("Canvas is unavailable.");
      context.drawImage(record.video, 0, 0, canvas.width, canvas.height);
      const capturedAt = new Date();
      const label = `${record.deviceId}  ${capturedAt.toLocaleString()}`;
      const fontSize = Math.max(18, Math.round(canvas.width / 64));
      context.font = `${fontSize}px "Microsoft YaHei UI", sans-serif`;
      const padding = Math.round(fontSize * 0.7);
      const barHeight = fontSize + padding * 2;
      context.fillStyle = "rgba(0, 0, 0, 0.58)";
      context.fillRect(0, canvas.height - barHeight, canvas.width, barHeight);
      context.fillStyle = "#ffffff";
      context.fillText(label, padding, canvas.height - padding);
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
          (value) => value ? resolve(value) : reject(new Error("PNG encoding failed.")),
          "image/png",
        );
      });
      const link = document.createElement("a");
      const stamp = capturedAt.toISOString().replace(/[:.]/g, "-");
      link.download = `${safeFilename(record.deviceId)}_${stamp}.png`;
      link.href = URL.createObjectURL(blob);
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      sendEvent("screenshot_succeeded", streamId, {
        width: canvas.width,
        height: canvas.height,
      });
      showNotice(`${record.deviceId} 当前画面已保存到本地。`, "success");
      return true;
    } catch {
      sendEvent("screenshot_failed", streamId, {}, "SCREENSHOT_FAILED");
      showNotice(ERROR_TEXT.screenshot_failed, "error");
      return false;
    }
  }

  function startHeartbeat() {
    stopHeartbeat();
    els.heartbeat.textContent = "正常";
    state.heartbeatTimer = setInterval(async () => {
      if (!state.sessionId) return;
      try {
        const session = await api(
          `sessions/${state.sessionId}/heartbeat`,
          {method: "POST"},
        );
        els.heartbeat.textContent = new Date(
          session.last_heartbeat_at,
        ).toLocaleTimeString();
        reconcileSession(session);
      } catch (error) {
        els.heartbeat.textContent = "异常";
        showNotice(`会话心跳异常：${friendlyError(error)}`, "error");
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  function stopHeartbeat() {
    if (state.heartbeatTimer) clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
  }

  function initializeTheme() {
    const saved = localStorage.getItem("cha-theme");
    document.documentElement.dataset.theme = saved === "light" ? "light" : "dark";
  }

  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "light"
      ? "dark"
      : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("cha-theme", next);
  }

  function cleanupOnExit() {
    state.pageLeaving = true;
    stopHeartbeat();
    if (state.sessionId) {
      fetch(apiPath(`sessions/${state.sessionId}`), {
        method: "DELETE",
        credentials: "same-origin",
        keepalive: true,
        headers: {"content-type": "application/json"},
      }).catch(() => {});
    }
    state.runtime?.close().catch(() => {});
    try {
      state.controlSocket?.close();
    } catch {}
  }

  els.theme.addEventListener("click", toggleTheme);
  els.refresh.addEventListener("click", () => loadDevices());
  els.search.addEventListener("input", renderDevices);
  els.filters.forEach((button) => {
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      els.filters.forEach((item) => item.classList.toggle("active", item === button));
      renderDevices();
    });
  });
  els.startSelected.addEventListener("click", startSelected);
  els.closeSession.addEventListener("click", () => closeSession());
  els.reconnect.addEventListener("click", () => reconnectSession());
  window.addEventListener("pagehide", cleanupOnExit);

  window.chaRealtimeInspection = {
    snapshot: () => ({
      session_id: state.sessionId,
      session_status: state.sessionStatus,
      max_streams: state.maxStreams,
      audio_supported: state.audioSupported,
      active_audio_stream_id: state.activeAudioStreamId,
      layout: activeTileCount() <= 1
        ? "single"
        : activeTileCount() <= 4 ? "quad" : "six",
      connection: els.connection.textContent,
      streams: [...state.tiles.values()].map((record) => ({
        stream_id: record.streamId,
        device_id: record.deviceId,
        status: record.status,
        resolution: record.resolution,
        track_state: record.trackState,
        first_frame_at: record.firstFrameAt,
        audio_status: record.audioStatus,
      })),
      runtime: state.runtime?.snapshot?.() || [],
    }),
    addDevice,
    closeTile,
    retryTile,
    toggleAudio,
    captureFrame,
    closeSession,
    loadDevices,
  };

  initializeTheme();
  updateSummary();
  loadDevices();
})();
