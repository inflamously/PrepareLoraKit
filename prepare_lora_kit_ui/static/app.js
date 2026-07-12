import { init } from "./core/app.js";
import { bootOnPywebviewReady } from "./core/boot.js";
import { installErrorSurface, runBoot } from "./core/errors.js";

installErrorSurface();
bootOnPywebviewReady(() => runBoot(init));
