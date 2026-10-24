// Le seul usage de swagger-ui-dist (src/docs.ts) : le paquet n'a pas de types, et
// @types/swagger-ui-dist décrit encore la version 3.
declare module "swagger-ui-dist/swagger-ui-es-bundle.js" {
  type Preset = unknown;
  type Config = {
    url: string;
    dom_id: string;
    presets: Preset[];
    layout: "BaseLayout";
    validatorUrl: null;
    persistAuthorization: boolean;
    tryItOutEnabled: boolean;
    deepLinking: boolean;
  };
  type Bundle = ((config: Config) => unknown) & { presets: { apis: Preset } };
  const SwaggerUIBundle: Bundle;
  export default SwaggerUIBundle;
}
