import { html } from "htm/preact";
import api from "../api/index.mjs";
import { FontSize } from "../appearance/Fonts.mjs";

export const DownloadButton = ({ logFile, label, fileName, fileContents }) => {
  return html`<button
    class="btn btn-outline-primary"
    style=${{ fontSize: FontSize.small, marginTop: "3em" }}
    onclick=${async () => {
      await api.download_file(logFile, fileName, fileContents);
    }}
  >
    ${label}
  </button>`;
};
