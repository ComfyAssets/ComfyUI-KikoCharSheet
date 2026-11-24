// "My uploads" section: + Upload tile, guidance panel, preview with 4:5 frame, upload cards and an
// in-panel delete confirm. Ported from the ai-pose-gallery fork's uploads-ui.js.
// Uploads go through ComfyUI's own /upload/image into input/charsheet/<lib>/ only.
import {
  UPLOAD_ACCEPT,
  UPLOAD_SUBFOLDER,
  formatUploadId,
  isValidUploadFile,
  isValidUploadName,
  sizeWarning,
  uploadThumbUrl,
} from "./lib/gallery.js";
import { el, errorText, thumbBox, thumbImage } from "./dom.js";

const COPIED_FEEDBACK_MS = 1500;
const PORTRAIT_TIPS = ["camera", "framing", "light", "background", "expression", "accessories", "hair"];

async function fetchUploads(api, lib) {
  const resp = await api.fetchApi(`/charsheet/uploads?lib=${encodeURIComponent(lib)}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  return Array.isArray(data?.items) ? data.items : [];
}

/** Upload one file; returns the name ComfyUI stored it under (it renames duplicates). */
async function postUpload(api, lib, file) {
  const form = new FormData();
  form.append("image", file, file.name);
  form.append("subfolder", `${UPLOAD_SUBFOLDER}/${lib}`);
  form.append("type", "input");
  const resp = await api.fetchApi("/upload/image", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  if (typeof data?.name !== "string" || !data.name) throw new Error("missing name in response");
  return data.name;
}

async function deleteUploadRequest(api, lib, name) {
  const resp = await api.fetchApi(`/charsheet/uploads/${encodeURIComponent(lib)}/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
}

/** CSS box (percent of the image) of the centred 4:5 frame inside an image of the given size. */
function frameBox(width, height) {
  const ratio = width / height;
  const target = 4 / 5;
  const w = ratio > target ? (target / ratio) * 100 : 100;
  const h = ratio > target ? 100 : (ratio / target) * 100;
  return { left: `${(100 - w) / 2}%`, top: `${(100 - h) / 2}%`, width: `${w}%`, height: `${h}%` };
}

export class UploadSection {
  /**
   * @param {{api: any, lib: string, t: Function, container: HTMLElement,
   *   getSelectedIds: () => string[], onPick: (id: string) => void, onDeleted: (id: string) => void}} deps
   */
  constructor({ api, lib, t, container, getSelectedIds, onPick, onDeleted }) {
    Object.assign(this, { api, lib, t, container, getSelectedIds, onPick, onDeleted });
    this.generation = 0; // bumped on destroy so stale async results are dropped
    this.previewUrl = null;
    this.copyTimer = null;

    this.panel = el("div", { class: "cs-upload-panel", hidden: true });
    this.title = el("div", { class: "cs-section-title", text: t("uploads.title") });
    this.message = el("div", { class: "cs-upload-message", hidden: true });
    this.row = el("div", { class: "cs-grid cs-upload-row" });
    this.fileInput = el("input", { type: "file", accept: UPLOAD_ACCEPT, hidden: true });
    this.fileInput.addEventListener("change", () => this.handleFileChosen());
    container.replaceChildren(this.title, this.panel, this.message, this.row, this.fileInput);
    this.refresh();
  }

  destroy() {
    this.generation += 1;
    this.revokePreview();
    clearTimeout(this.copyTimer);
  }

  async refresh() {
    const { generation } = this;
    this.renderRow([]);
    this.message.hidden = true;
    try {
      const items = await fetchUploads(this.api, this.lib);
      if (generation !== this.generation) return;
      this.renderRow(items);
      if (!items.length) this.showMessage(this.t("uploads.empty"), false);
    } catch (err) {
      if (generation !== this.generation) return;
      this.showMessage(this.t("uploads.listError", { error: errorText(err) }), true);
    }
  }

  showMessage(text, isError) {
    this.message.textContent = text;
    this.message.classList.toggle("cs-error-text", isError);
    this.message.hidden = false;
  }

  /** Highlight the upload cards whose ids are selected. */
  markSelected(ids = this.getSelectedIds()) {
    const chosen = new Set(ids);
    this.row.querySelectorAll(".cs-card[data-id]").forEach((card) => {
      const on = chosen.has(card.dataset.id);
      card.classList.toggle("cs-selected", on);
      card.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  renderRow(items) {
    const open = () => this.openGuide();
    const tile = el("div", { class: "cs-card cs-upload-tile", role: "button", tabindex: "0", onclick: open }, [
      el("div", { class: "cs-upload-plus", text: this.t("uploads.tile") }),
      el("div", { class: "cs-card-sub", text: this.t("uploads.tileHint") }),
    ]);
    tile.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
    this.row.replaceChildren(tile, ...items.map((item) => this.buildUploadCard(item)));
    this.markSelected();
  }

  buildUploadCard(item) {
    const id = formatUploadId(item.name);
    const img = thumbImage(this.api.apiURL(uploadThumbUrl(this.lib, item.name)), {
      alt: item.name,
      missingText: this.t("uploads.notFound"),
    });
    const removeBtn = el("button", {
      class: "cs-upload-remove",
      type: "button",
      title: this.t("uploads.deleteAria"),
      "aria-label": this.t("uploads.deleteAria"),
      text: "×",
    });
    const box = thumbBox(img);
    box.appendChild(removeBtn);
    const card = el("div", { class: "cs-card cs-upload-card", role: "button", tabindex: "0" }, [
      box,
      el("div", { class: "cs-card-title", title: item.name, text: item.name }),
      el("div", { class: "cs-card-sub", text: this.t("uploads.dimensions", { width: item.width, height: item.height }) }),
    ]);
    card.dataset.id = id;
    card.addEventListener("click", () => this.onPick(id));
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.showDeleteConfirm(box, item.name);
    });
    return card;
  }

  showDeleteConfirm(box, name) {
    if (box.querySelector(".cs-upload-confirm")) return;
    const { generation } = this;
    const status = el("div", { class: "cs-error-text", hidden: true });
    const deleteBtn = el("button", { class: "cs-btn cs-btn-danger", type: "button", text: this.t("uploads.delete") });
    const cancelBtn = el("button", { class: "cs-btn", type: "button", text: this.t("uploads.cancel") });
    const confirm = el("div", { class: "cs-upload-confirm", onclick: (e) => e.stopPropagation() }, [
      el("div", { text: this.t("uploads.deleteConfirm") }),
      el("div", { class: "cs-actions" }, [deleteBtn, cancelBtn]),
      status,
    ]);
    cancelBtn.addEventListener("click", () => confirm.remove());
    deleteBtn.addEventListener("click", async () => {
      deleteBtn.disabled = true;
      cancelBtn.disabled = true;
      try {
        await deleteUploadRequest(this.api, this.lib, name);
      } catch (err) {
        status.textContent = this.t("uploads.deleteError", { error: errorText(err) });
        status.hidden = false;
        deleteBtn.disabled = false;
        cancelBtn.disabled = false;
        return;
      }
      if (generation !== this.generation) return;
      this.onDeleted(formatUploadId(name));
      this.refresh();
    });
    box.appendChild(confirm);
  }

  // ---- Guidance panel and preview ----

  closePanel() {
    this.revokePreview();
    clearTimeout(this.copyTimer);
    this.panel.hidden = true;
    this.panel.replaceChildren();
  }

  revokePreview() {
    if (this.previewUrl) {
      URL.revokeObjectURL(this.previewUrl);
      this.previewUrl = null;
    }
  }

  openGuide(errorMessage = "") {
    this.revokePreview();
    const { lib, t } = this;
    const body = [el("div", { class: "cs-upload-panel-title", text: t(`uploads.guideTitle.${lib}`) })];
    if (lib === "portrait") {
      body.push(
        el("p", {}, [el("strong", { text: `${t("uploads.sizeLabel")}: ` }), t("uploads.size")]),
        el("div", { class: "cs-upload-label", text: t("uploads.tipsLabel") }),
        el("ul", { class: "cs-upload-tips" }, PORTRAIT_TIPS.map((key) => el("li", { text: t(`uploads.tips.${key}`) }))),
        this.buildPromptHelper()
      );
    } else {
      body.push(el("p", { text: t(lib === "costume" ? "uploads.costumeGuide" : "uploads.poseGuide") }));
    }
    body.push(
      el("div", { class: "cs-actions" }, [
        el("button", { class: "cs-btn cs-btn-primary", type: "button", text: t("uploads.choose"), onclick: () => this.chooseFile() }),
        el("button", { class: "cs-btn", type: "button", text: t("uploads.cancel"), onclick: () => this.closePanel() }),
      ]),
      el("div", { class: "cs-error-text", hidden: !errorMessage, text: errorMessage })
    );
    this.panel.replaceChildren(...body);
    this.panel.hidden = false;
  }

  buildPromptHelper() {
    const { t } = this;
    const promptText = el("textarea", { class: "cs-upload-prompt", readonly: true, rows: "3" });
    promptText.value = t("uploads.prompt");
    const feedback = el("span", { class: "cs-upload-feedback", "aria-live": "polite" });
    const copyBtn = el("button", { class: "cs-btn", type: "button", text: t("uploads.copy") });
    copyBtn.addEventListener("click", async () => {
      clearTimeout(this.copyTimer);
      try {
        if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
        await navigator.clipboard.writeText(promptText.value);
        feedback.textContent = t("uploads.copied");
        feedback.classList.remove("cs-error-text");
        this.copyTimer = setTimeout(() => {
          feedback.textContent = "";
        }, COPIED_FEEDBACK_MS);
      } catch {
        feedback.textContent = t("uploads.copyFailed");
        feedback.classList.add("cs-error-text");
        promptText.focus();
        promptText.select();
      }
    });
    return el("div", { class: "cs-upload-prompt-block" }, [
      el("div", { class: "cs-upload-label", text: t("uploads.promptLabel") }),
      promptText,
      el("div", { class: "cs-actions" }, [copyBtn, feedback]),
    ]);
  }

  chooseFile() {
    this.fileInput.value = "";
    this.fileInput.click();
  }

  handleFileChosen() {
    const file = this.fileInput.files?.[0];
    this.fileInput.value = "";
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (!UPLOAD_ACCEPT.split(",").some((ext) => lower.endsWith(ext))) {
      this.openGuide(this.t("uploads.badType"));
      return;
    }
    if (!isValidUploadFile(file)) {
      this.openGuide(this.t("uploads.badName"));
      return;
    }
    this.showPreview(file);
  }

  showPreview(file) {
    this.revokePreview();
    const { lib, t } = this;
    this.previewUrl = URL.createObjectURL(file);
    const img = el("img", { class: "cs-upload-preview-img", alt: file.name, src: this.previewUrl });
    const frame = el("div", { class: "cs-upload-frame", hidden: true });
    const warning = el("div", { class: "cs-warning-text", hidden: true });
    const error = el("div", { class: "cs-error-text", hidden: true });
    img.addEventListener("load", () => {
      if (sizeWarning(img.naturalWidth)) {
        warning.textContent = t("uploads.sizeWarning", { width: img.naturalWidth });
        warning.hidden = false;
      }
      if (lib === "portrait" && img.naturalWidth && img.naturalHeight) {
        Object.assign(frame.style, frameBox(img.naturalWidth, img.naturalHeight));
        frame.hidden = false;
      }
    });
    const useBtn = el("button", { class: "cs-btn cs-btn-primary", type: "button", text: t("uploads.use") });
    const cancelBtn = el("button", { class: "cs-btn", type: "button", text: t("uploads.cancel"), onclick: () => this.openGuide() });
    useBtn.addEventListener("click", () => this.upload(file, { useBtn, cancelBtn, error }));
    this.panel.replaceChildren(
      el("div", { class: "cs-upload-panel-title", text: t(`uploads.guideTitle.${lib}`) }),
      el("div", { class: "cs-upload-preview" }, [img, frame]),
      lib === "portrait" ? el("div", { class: "cs-card-sub", text: t("uploads.frameNote") }) : null,
      warning,
      el("div", { class: "cs-actions" }, [useBtn, cancelBtn]),
      error
    );
    this.panel.hidden = false;
  }

  failUpload(message, { useBtn, cancelBtn, error }) {
    error.textContent = message;
    error.hidden = false;
    useBtn.disabled = false;
    cancelBtn.disabled = false;
    useBtn.textContent = this.t("uploads.use");
  }

  async upload(file, controls) {
    const { generation } = this;
    controls.useBtn.disabled = true;
    controls.cancelBtn.disabled = true;
    controls.useBtn.textContent = this.t("uploads.uploading");
    controls.error.hidden = true;
    let name;
    try {
      name = await postUpload(this.api, this.lib, file);
    } catch (err) {
      if (generation === this.generation) this.failUpload(this.t("uploads.uploadError", { error: errorText(err) }), controls);
      return;
    }
    if (generation !== this.generation) return;
    if (!isValidUploadName(name)) {
      this.failUpload(this.t("uploads.badStoredName", { name }), controls);
      return;
    }
    this.closePanel();
    await this.refresh();
    if (generation !== this.generation) return;
    // ComfyUI may return an existing name for identical content: ask the panel to add, never toggle off.
    this.onPick(formatUploadId(name), { ensure: true });
  }
}
