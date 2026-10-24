import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { initLanguage } from "./i18n/language";
import "./index.css";
import { initTheme } from "./theme";

initTheme();
initLanguage();

const root = document.getElementById("root");

if (root === null) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
