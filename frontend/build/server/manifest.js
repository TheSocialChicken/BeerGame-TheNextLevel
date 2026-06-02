const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.7z37ZPCO.js",app:"_app/immutable/entry/app.BcNNKV-Y.js",imports:["_app/immutable/entry/start.7z37ZPCO.js","_app/immutable/chunks/DfNJuWCO.js","_app/immutable/chunks/CsEKCgSH.js","_app/immutable/chunks/BnHrocuu.js","_app/immutable/entry/app.BcNNKV-Y.js","_app/immutable/chunks/CsEKCgSH.js","_app/immutable/chunks/O6w-R4gp.js","_app/immutable/chunks/DDjXQvNW.js","_app/immutable/chunks/BnHrocuu.js","_app/immutable/chunks/DD1HIcZq.js","_app/immutable/chunks/DCyHJRwJ.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./chunks/0-xJPfYr9g.js')),
			__memo(() => import('./chunks/1-CFo7mu5N.js')),
			__memo(() => import('./chunks/2-BQ6PTCpA.js')),
			__memo(() => import('./chunks/3-C_oukZFx.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/game/[id]/[role]",
				pattern: /^\/game\/([^/]+?)\/([^/]+?)\/?$/,
				params: [{"name":"id","optional":false,"rest":false,"chained":false},{"name":"role","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();

const prerendered = new Set([]);

const base = "";

export { base, manifest, prerendered };
//# sourceMappingURL=manifest.js.map
