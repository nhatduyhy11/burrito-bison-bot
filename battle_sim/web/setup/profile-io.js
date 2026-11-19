// Setup page state <-> profile JSON (the format web/battle/profile.js reads).
// Entry point re-exporting the split modules: profile-state.js (state shape + normalize),
// profile-export.js (toProfile), profile-import.js (fromProfile).
export * from "./profile-state.js";
export { toProfile } from "./profile-export.js";
export { fromProfile } from "./profile-import.js";
