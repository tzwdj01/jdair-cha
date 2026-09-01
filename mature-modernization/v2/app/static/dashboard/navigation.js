(() => {
  "use strict";

  const root = document.querySelector("[data-cha-dashboard-nav]");
  if (!root) return;

  const entries = [
    { id: "overview", label: "监察总览", href: "/api/v2/dashboard", active: ["overview"] },
    { id: "workbench", label: "视频监察", href: "/api/v2/dashboard/workbench", active: ["workbench"] },
    { id: "legacy", label: "经典视频监控", href: "/", active: [] },
    { id: "inspections", label: "监察记录", href: "/api/v2/dashboard/inspections", active: ["inspections"] },
    { id: "devices", label: "设备运行", href: "/api/v2/dashboard/devices", active: ["devices"] },
    { id: "media", label: "视频上传", href: "/api/v2/dashboard/media", active: ["media"] },
    { id: "realtime", label: "监察使用", href: "/api/v2/dashboard/realtime", active: ["realtime"] },
    { id: "alarms", label: "告警异常", href: "/api/v2/dashboard/alarms", active: ["alarms"] },
    { id: "tasks", label: "航班/任务", href: "/api/v2/dashboard/tasks", active: ["tasks", "flights_tasks"] },
    { id: "map", label: "设备定位", href: "/api/v2/dashboard/map", active: ["map", "locations"] },
    { id: "data-quality", label: "数据质量", href: "/api/v2/dashboard/data-quality", active: ["data-quality", "data_quality"] },
  ];
  const active = root.dataset.active || "";

  const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
  const renderLink = (entry) => {
    const selected = entry.active.includes(active);
    return `<a class="cha-dashboard-nav-link${selected ? " is-active" : ""}" href="${entry.href}"${selected ? ' aria-current="page"' : ""}>${esc(entry.label)}</a>`;
  };

  if (!document.getElementById("cha-dashboard-nav-styles")) {
    const style = document.createElement("style");
    style.id = "cha-dashboard-nav-styles";
    style.textContent = `
      .cha-dashboard-nav { display:flex; gap:7px; flex-wrap:wrap; align-items:center; padding:9px 18px; background:#0f304c; border-top:1px solid rgba(255,255,255,.14); box-shadow:0 1px 0 rgba(0,0,0,.14); }
      .cha-dashboard-nav-link { display:inline-flex; align-items:center; min-height:31px; border:1px solid #276b9d; border-radius:4px; padding:5px 9px; color:#fff; background:#287bb6; text-decoration:none; font:13px/1.25 "Microsoft YaHei",Arial,sans-serif; white-space:nowrap; }
      .cha-dashboard-nav-link:hover { background:#1d689e; }
      .cha-dashboard-nav-link.is-active { color:#12395a; background:#fff; border-color:#fff; font-weight:700; }
      @media (max-width:760px) { .cha-dashboard-nav { padding:8px 14px; gap:6px; } .cha-dashboard-nav-link { padding:5px 8px; font-size:12px; } }
    `;
    document.head.appendChild(style);
  }

  root.classList.add("cha-dashboard-nav");
  root.setAttribute("aria-label", "CHA 生产功能导航");
  root.innerHTML = entries.map(renderLink).join("");

  // The server remains the authority: only an existing admin-only API response
  // can reveal the management link. The client never grants or changes access.
  fetch("/api/v2/inspections/authorized-users", { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) return;
      const selected = active === "users";
      const link = document.createElement("a");
      link.className = "cha-dashboard-nav-link" + (selected ? " is-active" : "");
      link.href = "/api/v2/dashboard/users";
      link.textContent = "用户权限";
      if (selected) link.setAttribute("aria-current", "page");
      root.appendChild(link);
    })
    .catch(() => {
      // The management link remains absent unless server-side admin access is proven.
    });
})();
