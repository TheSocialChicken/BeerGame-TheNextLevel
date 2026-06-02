

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/fallbacks/layout.svelte.js')).default;
export const imports = ["_app/immutable/nodes/0.TZOm-4V4.js","_app/immutable/chunks/DDjXQvNW.js","_app/immutable/chunks/CsEKCgSH.js","_app/immutable/chunks/DCyHJRwJ.js"];
export const stylesheets = [];
export const fonts = [];
