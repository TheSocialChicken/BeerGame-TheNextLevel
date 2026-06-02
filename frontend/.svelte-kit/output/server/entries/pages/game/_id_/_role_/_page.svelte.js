import { c as ssr_context, g as getContext, e as escape_html, d as derived, f as store_get, u as unsubscribe_stores } from "../../../../../chunks/root.js";
import "clsx";
import "@sveltejs/kit/internal";
import "../../../../../chunks/exports.js";
import "../../../../../chunks/utils2.js";
import "@sveltejs/kit/internal/server";
import "../../../../../chunks/state.svelte.js";
function onDestroy(fn) {
  /** @type {SSRContext} */
  ssr_context.r.on_destroy(fn);
}
const getStores = () => {
  const stores$1 = getContext("__svelte__");
  return {
    /** @type {typeof page} */
    page: {
      subscribe: stores$1.page.subscribe
    },
    /** @type {typeof navigating} */
    navigating: {
      subscribe: stores$1.navigating.subscribe
    },
    /** @type {typeof updated} */
    updated: stores$1.updated
  };
};
const page = {
  subscribe(fn) {
    const store = getStores().page;
    return store.subscribe(fn);
  }
};
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    const role = derived(() => store_get($$store_subs ??= {}, "$page", page).params.role);
    let statusMsg = "Connecting...";
    let socket = null;
    onDestroy(() => socket?.disconnect());
    $$renderer2.push(`<div class="board svelte-1gfiwxy"><header class="svelte-1gfiwxy"><h1 class="svelte-1gfiwxy">Beer Game — <span class="role svelte-1gfiwxy">${escape_html(role())}</span></h1> <p>Round ${escape_html("–")} · Phase: <strong>${escape_html("–")}</strong></p></header> `);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> `);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> <p class="status svelte-1gfiwxy">${escape_html(statusMsg)}</p></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
