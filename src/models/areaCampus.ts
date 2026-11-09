export interface CoordenadaMapa {
  latitude: number
  longitude: number
}

export interface AreaCampus {
  id: string
  nome: string
  tipo: string
  coordenadas: CoordenadaMapa[]
  limiteCampus: boolean
  prioridade: number
}

export interface DadosAreaCampus {
  nome: string
  tipo: string
  coordenadas: CoordenadaMapa[]
  limiteCampus: boolean
  prioridade: number
}

export interface LocalizacaoIdentificada {
  dentroCampus: boolean
  area: AreaCampus | null
  blocoMaisProximo: AreaCampus | null
  local: string
}
