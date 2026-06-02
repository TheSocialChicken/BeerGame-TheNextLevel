import { J as attr, K as ensure_array_like, E as escape_html } from './root-DXDo4eyu.js';
import './state.svelte-McpeHnJA.js';

function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let sessionId = "";
    let role = "retailer";
    const roles = ["retailer", "wholesaler", "distributor", "factory"];
    $$renderer2.push(`<div class="lobby svelte-1uha8ag"><h1 class="svelte-1uha8ag">🍺 Beer Game</h1> <p class="svelte-1uha8ag">Supply chain simulation — 4 players, 26 rounds</p> <button class="svelte-1uha8ag">New Game</button> <hr class="svelte-1uha8ag"/> <h2>Join existing game</h2> <input${attr("value", sessionId)} placeholder="Session ID" type="text" class="svelte-1uha8ag"/> `);
    $$renderer2.select(
      { value: role, class: "" },
      ($$renderer3) => {
        $$renderer3.push(`<!--[-->`);
        const each_array = ensure_array_like(roles);
        for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
          let r = each_array[$$index];
          $$renderer3.option({ value: r }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(r.charAt(0).toUpperCase() + r.slice(1))}`);
          });
        }
        $$renderer3.push(`<!--]-->`);
      },
      "svelte-1uha8ag"
    );
    $$renderer2.push(` <button class="svelte-1uha8ag">Join</button></div>`);
  });
}

export { _page as default };
//# sourceMappingURL=_page.svelte-DXjf7qWa.js.map
