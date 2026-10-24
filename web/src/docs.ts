// La page /api/docs (ADR 0021) : Swagger UI sur le document public de l'API, servi par l'API.
// Tout vient de la même origine : aucun script ni style inline, aucun CDN (CSP de la page).
// Le bundle seul, sans index.js du paquet (qui lit le disque, pour Node).
import SwaggerUIBundle from "swagger-ui-dist/swagger-ui-es-bundle.js";
import "swagger-ui-dist/swagger-ui.css";

SwaggerUIBundle({
  url: "/api/v1/openapi.json",
  dom_id: "#swagger",
  presets: [SwaggerUIBundle.presets.apis],
  layout: "BaseLayout",
  // Aucun appel au validateur en ligne de swagger.io.
  validatorUrl: null,
  // Le jeton saisi reste dans la page, jamais dans le stockage du navigateur.
  persistAuthorization: false,
  tryItOutEnabled: false,
  deepLinking: true,
});
