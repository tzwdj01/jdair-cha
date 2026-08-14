const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

global.window = {};
const runtimePath = path.resolve(
  __dirname,
  "../app/static/realtime/multistream_runtime.js",
);
vm.runInThisContext(fs.readFileSync(runtimePath, "utf8"), {
  filename: runtimePath,
});

class MediaElement {
  constructor() {
    this.listeners = new Map();
    this.srcObject = null;
    this.paused = false;
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) this.listeners.delete(name);
  }

  pause() {
    this.paused = true;
  }

  removeAttribute() {}

  load() {}
}

async function testOfflineNormalizationAndCleanup() {
  const runtime = new window.ChaRealtimeMultiStreamRuntime({
    gatewayPath: "/unused",
  });
  let closeCalls = 0;
  runtime.connected = true;
  runtime.client = {
    async openVideo() {
      throw new Error('devices is offline request.method "mediaMonitor"');
    },
    async closeVideo(deviceId, channelId, serverId) {
      assert.equal(deviceId, "WXB358");
      assert.equal(channelId, "");
      assert.equal(serverId, "");
      closeCalls += 1;
      return 200;
    },
  };
  const video = new MediaElement();
  const audio = new MediaElement();

  await assert.rejects(
    runtime.openStream({
      streamId: "stream-offline",
      deviceId: "WXB358",
      videoElement: video,
      audioElement: audio,
    }),
    (error) => {
      assert.equal(error.code, "DEVICE_MEDIA_OFFLINE");
      assert.equal(
        error.message,
        "The AEE media service reports that the device media channel is offline.",
      );
      return true;
    },
  );

  assert.equal(closeCalls, 1);
  assert.equal(runtime.streams.size, 0);
  assert.equal(video.listeners.size, 0);
  assert.equal(video.srcObject, null);
  assert.equal(video.paused, true);
}

async function testUnknownErrorIsPreserved() {
  const runtime = new window.ChaRealtimeMultiStreamRuntime({
    gatewayPath: "/unused",
  });
  const original = new Error("unexpected upstream failure");
  original.code = "UPSTREAM_TEST_ERROR";
  runtime.connected = true;
  runtime.client = {
    async openVideo() {
      throw original;
    },
    async closeVideo() {
      return 200;
    },
  };

  await assert.rejects(
    runtime.openStream({
      streamId: "stream-other",
      deviceId: "WXB353",
      videoElement: new MediaElement(),
      audioElement: new MediaElement(),
    }),
    (error) => error === original,
  );
}

async function testCompensatingCloseFailureDoesNotMaskOfflineError() {
  const runtime = new window.ChaRealtimeMultiStreamRuntime({
    gatewayPath: "/unused",
  });
  runtime.connected = true;
  runtime.client = {
    async openVideo() {
      throw new Error('devices is offline request.method "mediaMonitor"');
    },
    async closeVideo() {
      throw new Error("close failed");
    },
  };

  await assert.rejects(
    runtime.openStream({
      streamId: "stream-close-failure",
      deviceId: "WXB358",
      videoElement: new MediaElement(),
      audioElement: new MediaElement(),
    }),
    (error) => error.code === "DEVICE_MEDIA_OFFLINE",
  );
  assert.equal(runtime.streams.size, 0);
}

(async () => {
  await testOfflineNormalizationAndCleanup();
  await testUnknownErrorIsPreserved();
  await testCompensatingCloseFailureDoesNotMaskOfflineError();
  process.stdout.write("realtime runtime tests passed\n");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
