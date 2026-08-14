(() => {
  "use strict";

  class ChaRealtimeMultiStreamRuntime {
    constructor({gatewayPath, onEvent = () => {}}) {
      this.gatewayPath = gatewayPath;
      this.onEvent = onEvent;
      this.client = null;
      this.connected = false;
      this.connectionError = null;
      this.streams = new Map();
      this.connectPromise = null;
    }

    configure({gatewayPath}) {
      if (gatewayPath && !this.client) this.gatewayPath = gatewayPath;
    }

    websocketSettings() {
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
        httpProxy: this.gatewayPath,
        localVideo: null,
        localAudio: null,
      };
    }

    async connect(timeoutMs = 15000) {
      if (this.connected && this.client) return;
      if (this.connectPromise) return this.connectPromise;
      this.connectPromise = new Promise((resolve, reject) => {
        if (typeof window.mcs8Client !== "function") {
          reject(new Error("AEE SDK is unavailable."));
          return;
        }
        const client = new window.mcs8Client();
        this.client = client;
        this.connectionError = null;
        const timer = setTimeout(() => {
          const error = new Error("AEE media room connection timed out.");
          error.code = "UPSTREAM_CONNECTION_FAILED";
          reject(error);
        }, timeoutMs);
        client.on("OnManage", (event) => {
          const method = event?.method || "";
          const code = Number(event?.errCode || 0);
          this.onEvent({event: "aee_manage", method, code});
          if (method === "joinRoom" && code === 200) {
            clearTimeout(timer);
            this.connected = true;
            resolve();
          } else if (code && code !== 200) {
            clearTimeout(timer);
            const error = new Error(`${method || "AEE"} failed.`);
            error.code = "AEE_CONNECT_FAILED";
            this.connectionError = error;
            reject(error);
          }
        });
        client.connect(this.websocketSettings());
      }).finally(() => {
        this.connectPromise = null;
      });
      return this.connectPromise;
    }

    async openStream({streamId, deviceId, videoElement, audioElement}) {
      if (!streamId || !deviceId || !videoElement || !audioElement) {
        throw new Error("streamId, deviceId and media elements are required.");
      }
      if (this.streams.has(streamId)) {
        throw new Error("The stream is already registered.");
      }
      await this.connect();
      const record = {
        streamId,
        deviceId,
        videoElement,
        audioElement,
        status: "WAITING_FIRST_FRAME",
        audioStatus: "OFF",
        onLoaded: null,
      };
      record.onLoaded = () => {
        if (!videoElement.videoWidth) return;
        record.status = "PLAYING";
        const track =
          videoElement.srcObject?.getVideoTracks?.()[0] || null;
        this.onEvent({
          event: "first_frame",
          stream_id: streamId,
          device_id: deviceId,
          width: videoElement.videoWidth,
          height: videoElement.videoHeight,
          track_state: track?.readyState || null,
        });
      };
      videoElement.addEventListener("loadeddata", record.onLoaded);
      this.streams.set(streamId, record);
      let result;
      try {
        result = await this.client.openVideo(
          deviceId,
          videoElement,
          "",
          "",
        );
      } catch (error) {
        videoElement.removeEventListener("loadeddata", record.onLoaded);
        this.stopElement(videoElement);
        this.streams.delete(streamId);
        throw error;
      }
      if (result !== 200) {
        videoElement.removeEventListener("loadeddata", record.onLoaded);
        this.stopElement(videoElement);
        this.streams.delete(streamId);
        const error = new Error(`openVideo returned ${result}`);
        error.code = "OPEN_VIDEO_REJECTED";
        throw error;
      }
      this.onEvent({
        event: "open_video_accepted",
        stream_id: streamId,
        device_id: deviceId,
      });
      return record;
    }

    hasStream(streamId) {
      return this.streams.has(streamId);
    }

    markFailed(streamId) {
      const record = this.streams.get(streamId);
      if (record) record.status = "FAILED";
    }

    async closeStream(streamId) {
      const record = this.streams.get(streamId);
      if (!record) return {closed: false, reason: "not_found"};
      if (record.audioStatus !== "OFF") {
        try {
          await this.closeAudio(streamId);
        } catch {
          this.stopElement(record.audioElement);
          record.audioStatus = "OFF";
        }
      }
      const result = await this.client.closeVideo(
        record.deviceId,
        "",
        "",
      );
      if (![200, 404].includes(result)) {
        const error = new Error(`closeVideo returned ${result}`);
        error.code = "CLOSE_VIDEO_REJECTED";
        throw error;
      }
      record.videoElement.removeEventListener(
        "loadeddata",
        record.onLoaded,
      );
      this.stopElement(record.videoElement);
      record.status = "CLOSED";
      this.streams.delete(streamId);
      this.onEvent({
        event: "stream_closed",
        stream_id: streamId,
        device_id: record.deviceId,
      });
      return {closed: true, result};
    }

    async openAudio(streamId, timeoutMs = 15000) {
      const record = this.streams.get(streamId);
      if (!record) throw new Error("The video stream is not registered.");
      if (record.audioStatus === "PLAYING") return record;
      record.audioStatus = "OPENING";
      record.audioElement.muted = true;
      const result = await this.client.openAudio(
        record.deviceId,
        record.audioElement,
        "",
        "",
      );
      if (result !== 200) {
        record.audioStatus = "FAILED";
        const error = new Error(`openAudio returned ${result}`);
        error.code = "AUDIO_OPEN_FAILED";
        throw error;
      }
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        const track = record.audioElement.srcObject?.getAudioTracks?.()[0];
        if (track?.readyState === "live") {
          record.audioElement.muted = false;
          await record.audioElement.play();
          record.audioStatus = "PLAYING";
          const media = this.client?._mediaClientList?.get?.("mcs8_admin");
          const consumers = media?._consumerList
            ? Array.from(media._consumerList.values())
            : [];
          const consumer = [...consumers].reverse().find(
            (item) => item?.kind === "audio" || item?.track?.kind === "audio",
          );
          const codec =
            consumer?.rtpParameters?.codecs?.[0]?.mimeType || null;
          this.onEvent({
            event: "audio_playing",
            stream_id: streamId,
            device_id: record.deviceId,
            track_state: track.readyState,
            codec,
          });
          return record;
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      record.audioStatus = "FAILED";
      const error = new Error("Realtime audio track timed out.");
      error.code = "AUDIO_OPEN_FAILED";
      throw error;
    }

    async closeAudio(streamId) {
      const record = this.streams.get(streamId);
      if (!record || record.audioStatus === "OFF") {
        return {closed: false, reason: "not_open"};
      }
      const result = await this.client.closeAudio(
        record.deviceId,
        "",
        "",
      );
      if (![200, 404].includes(result)) {
        const error = new Error(`closeAudio returned ${result}`);
        error.code = "AUDIO_RELEASE_FAILED";
        throw error;
      }
      record.audioElement.muted = true;
      this.stopElement(record.audioElement);
      record.audioStatus = "OFF";
      this.onEvent({
        event: "audio_closed",
        stream_id: streamId,
        device_id: record.deviceId,
      });
      return {closed: true, result};
    }

    async handleControlCommand(message) {
      if (message?.action === "close_stream") {
        return this.closeStream(message.payload?.stream_id || "");
      }
      if (message?.action === "close_audio") {
        return this.closeAudio(message.payload?.stream_id || "");
      }
      if (message?.action === "close_session") {
        await this.close();
        return {closed: true};
      }
      const error = new Error("Unsupported realtime control command.");
      error.code = "CONTROL_COMMAND_UNSUPPORTED";
      throw error;
    }

    async close() {
      for (const streamId of [...this.streams.keys()].reverse()) {
        try {
          await this.closeStream(streamId);
        } catch {
          const record = this.streams.get(streamId);
          if (record) this.stopElement(record.videoElement);
          this.streams.delete(streamId);
        }
      }
      const client = this.client;
      this.client = null;
      this.connected = false;
      this.connectionError = null;
      if (client) {
        await client.close();
        client.removeAllListeners?.("OnManage");
      }
    }

    snapshot() {
      return [...this.streams.values()].map((record) => ({
        stream_id: record.streamId,
        device_id: record.deviceId,
        status: record.status,
        audio_status: record.audioStatus,
        track_state:
          record.videoElement.srcObject?.getVideoTracks?.()[0]?.readyState
          || null,
      }));
    }

    stopElement(mediaElement) {
      const mediaStream = mediaElement?.srcObject;
      if (mediaStream) {
        for (const track of mediaStream.getTracks()) track.stop();
      }
      if (!mediaElement) return;
      mediaElement.pause?.();
      mediaElement.srcObject = null;
      mediaElement.removeAttribute?.("src");
      mediaElement.load?.();
    }
  }

  window.ChaRealtimeMultiStreamRuntime = ChaRealtimeMultiStreamRuntime;
})();
