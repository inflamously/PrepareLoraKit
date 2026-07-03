import { init } from "./core/app.js";
import { installErrorSurface, runBoot } from "./core/errors.js";

installErrorSurface();

globalThis.addEventListener("pywebviewready", () => runBoot(init));
