/* Cloudflare Web Analytics: manual installation for the public personal website. */
(() => {
  "use strict";
  // Do not measure local previews, GitHub's direct hostname or the private dashboard.
  if (!["a-samadi.com", "www.a-samadi.com"].includes(window.location.hostname)) return;
  if (document.querySelector("script[data-cf-beacon]")) return;
  const beacon = document.createElement("script");
  beacon.type = "module";
  beacon.src = "https://static.cloudflareinsights.com/beacon.min.js";
  // This public site token is copied from the owner-account installation snippet.
  beacon.setAttribute("data-cf-beacon", '{"token": "8c7ffba813244de3acba6fd4bb874c0b"}');
  document.head.appendChild(beacon);
})();
