// ComfyUI extension entry: mounts the in-node picker panels and the Pose Sheet Designer panel.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { getTranslator, installPanel, syncInstalled } from "./mount.js";

app.registerExtension({
  name: "charsheet.Pickers",
  setup() {
    getTranslator(app, api); // start loading strings early
  },
  nodeCreated(node) {
    installPanel(node, app, api);
  },
  afterConfigureGraph() {
    for (const node of app.graph?._nodes ?? []) syncInstalled(node);
  },
});
