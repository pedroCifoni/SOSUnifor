/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_SOS_USAR_GPS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
