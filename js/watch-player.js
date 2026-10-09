/* Timestamp deep links used by VideoObject SeekToAction on the watch pages. */
(() => {
  'use strict';
  const value = new URLSearchParams(window.location.search).get('t');
  if (value === null || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)) return;
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return;

  document.querySelectorAll('video[data-watch-player]').forEach(video => {
    let finished = false;
    let pending = false;
    let target = 0;
    const events = ['loadedmetadata', 'loadeddata', 'canplay', 'progress'];
    const finish = () => {
      finished = true;
      events.forEach(event => video.removeEventListener(event, seek));
      video.removeEventListener('seeked', confirm);
      video.removeEventListener('seeking', userSeek);
    };
    const confirm = () => {
      if (pending && Math.abs(video.currentTime - target) < 0.1) finish();
      pending = false;
    };
    const userSeek = () => {
      // A visitor who moves the native timeline takes control of the position.
      if (!pending) finish();
    };
    const seek = () => {
      if (finished || pending || video.readyState < 1 || !Number.isFinite(video.duration) || video.duration <= 0) return;
      target = Math.min(seconds, Math.max(0, video.duration - 0.1));
      if (Math.abs(video.currentTime - target) < 0.1) {
        finish();
        return;
      }
      // Metadata can arrive before the server makes the target range seekable.
      const ranges = video.seekable;
      let available = false;
      for (let i = 0; i < ranges.length; i++) {
        if (ranges.start(i) <= target && ranges.end(i) >= target) available = true;
      }
      if (!available) return;
      pending = true;
      try {
        video.currentTime = target;
        if (!video.seeking) confirm();
      } catch (_) {
        pending = false;
      }
    };
    events.forEach(event => video.addEventListener(event, seek));
    video.addEventListener('seeked', confirm);
    video.addEventListener('seeking', userSeek);
    seek();
  });
})();
