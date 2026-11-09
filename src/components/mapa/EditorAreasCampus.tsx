import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import { TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { AreaCampus, CoordenadaMapa } from '@/models/areaCampus'

interface EditorAreasCampusProps {
  areas: AreaCampus[]
  coordenadasIniciais: CoordenadaMapa[]
  aoAlterarCoordenadas: (coordenadas: CoordenadaMapa[]) => void
}

const CENTRO_UNIFOR: [number, number] = [-38.478061, -3.7687753]
const ESTILO_MAPA_PADRAO = {
  version: 8 as const,
  sources: {
    mapaBase: {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'mapa-base', type: 'raster' as const, source: 'mapaBase' }],
}
const ESTILO_MAPA = import.meta.env.VITE_MAP_STYLE_URL ?? ESTILO_MAPA_PADRAO

function criarPoligono(coordenadas: CoordenadaMapa[]) {
  const pontos = coordenadas.map((ponto) => [ponto.longitude, ponto.latitude])
  if (pontos.length > 0) pontos.push(pontos[0])
  return {
    type: 'Feature' as const,
    properties: { mode: 'polygon' },
    geometry: { type: 'Polygon' as const, coordinates: [pontos] },
  }
}

function extrairCoordenadas(desenho: TerraDraw): CoordenadaMapa[] {
  const poligono = desenho.getSnapshot().find((item) => item.geometry.type === 'Polygon')
  if (!poligono || poligono.geometry.type !== 'Polygon') return []
  const pontos = poligono.geometry.coordinates[0]
  return pontos.slice(0, -1).map(([longitude, latitude]) => ({ latitude, longitude }))
}

function criarColecaoDeAreas(areas: AreaCampus[]) {
  return {
    type: 'FeatureCollection' as const,
    features: areas.map((area) => ({
      type: 'Feature' as const,
      properties: {
        nome: area.nome,
        limiteCampus: area.limiteCampus,
        cor: area.tipo === 'area_verde' || area.tipo === 'area_externa' ? '#16a34a' : '#155eef',
      },
      geometry: { type: 'Polygon' as const, coordinates: [[...area.coordenadas.map((ponto) => [ponto.longitude, ponto.latitude]), [area.coordenadas[0].longitude, area.coordenadas[0].latitude]]] },
    })),
  }
}

export function EditorAreasCampus({ areas, coordenadasIniciais, aoAlterarCoordenadas }: EditorAreasCampusProps) {
  const elementoMapa = useRef<HTMLDivElement | null>(null)
  const mapa = useRef<maplibregl.Map | null>(null)
  const desenho = useRef<TerraDraw | null>(null)
  const aoAlterar = useRef(aoAlterarCoordenadas)
  const areasAtuais = useRef(areas)
  aoAlterar.current = aoAlterarCoordenadas
  areasAtuais.current = areas

  useEffect(() => {
    if (!elementoMapa.current) return
    const novoMapa = new maplibregl.Map({
      container: elementoMapa.current,
      style: ESTILO_MAPA,
      center: CENTRO_UNIFOR,
      zoom: 15,
    })
    novoMapa.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapa.current = novoMapa

    novoMapa.on('load', () => {
      novoMapa.addSource('areas-cadastradas', { type: 'geojson', data: criarColecaoDeAreas(areasAtuais.current) })
      novoMapa.addLayer({
        id: 'preenchimento-areas-cadastradas',
        type: 'fill',
        source: 'areas-cadastradas',
        paint: { 'fill-color': ['get', 'cor'], 'fill-opacity': 0.2 },
      })
      novoMapa.addLayer({
        id: 'contorno-areas-cadastradas',
        type: 'line',
        source: 'areas-cadastradas',
        paint: { 'line-color': ['get', 'cor'], 'line-width': 2 },
      })

      const novoDesenho = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map: novoMapa }),
        modes: [new TerraDrawPolygonMode(), new TerraDrawSelectMode()],
      })
      novoDesenho.start()
      if (coordenadasIniciais.length >= 3) {
        novoDesenho.addFeatures([criarPoligono(coordenadasIniciais)])
        novoDesenho.setMode('select')
      } else {
        novoDesenho.setMode('polygon')
      }
      novoDesenho.on('change', () => aoAlterar.current(extrairCoordenadas(novoDesenho)))
      novoDesenho.on('finish', () => {
        aoAlterar.current(extrairCoordenadas(novoDesenho))
        novoDesenho.setMode('select')
      })
      desenho.current = novoDesenho
    })

    return () => {
      desenho.current?.stop()
      desenho.current = null
      novoMapa.remove()
      mapa.current = null
    }
  }, [])

  useEffect(() => {
    const fonte = mapa.current?.getSource('areas-cadastradas') as maplibregl.GeoJSONSource | undefined
    fonte?.setData(criarColecaoDeAreas(areas))
  }, [areas])

  function iniciarDesenho() {
    desenho.current?.clear()
    desenho.current?.setMode('polygon')
    aoAlterarCoordenadas([])
  }

  function limparDesenho() {
    desenho.current?.clear()
    aoAlterarCoordenadas([])
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line p-3">
        <div>
          <h2 className="text-sm font-bold text-brand-900">Desenhe o limite da área</h2>
          <p className="text-xs text-muted">Clique nos vértices e feche no primeiro ponto. Depois, arraste para ajustar.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={iniciarDesenho} className="h-9 rounded-lg bg-brand-900 px-3 text-xs font-semibold text-white hover:bg-brand-700">Desenhar</button>
          <button onClick={limparDesenho} className="h-9 rounded-lg bg-brand-50 px-3 text-xs font-semibold text-brand-900 hover:bg-brand-100">Limpar</button>
        </div>
      </div>
      <div ref={elementoMapa} className="h-[420px] w-full" />
    </section>
  )
}
