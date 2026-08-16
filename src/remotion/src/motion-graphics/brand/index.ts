// Spec adapters for the two SPEC-BUILT components (D name-plate, F end-card).
// Deliberately NOT re-exported from ../index.ts: the motion-graphics barrel is
// the inventory of NAMED components, and cert_component_completeness.py reports
// anything exported there but absent from a dispatch map as dead code. These
// are dispatch WRAPPERS, not components — they belong to PromptlyRender's MG_MAP
// and nowhere else.
export { NamePlateMG, EndCardMG } from "./BrandSpecMG";
export { NAME_PLATE_STYLE_MAP, END_CARD_STYLE_MAP } from "./BrandSpecMG";
export type { NamePlateSpec, EndCardSpec } from "./BrandSpecMG";
