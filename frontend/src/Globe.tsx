import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { feature } from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import landData from 'world-atlas/land-110m.json'

type LandTopology = Topology<{ land: GeometryCollection }>

export default function Globe() {
  const host = useRef<HTMLDivElement>(null)
  const turn = useRef<((direction: number) => void) | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    const container = host.current
    if (!container) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      setUnavailable(true)
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    container.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100)
    camera.position.set(0, 0, 4.5)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enablePan = false
    controls.enableZoom = false
    controls.enableDamping = false
    controls.rotateSpeed = 0.6
    controls.minPolarAngle = 0.2
    controls.maxPolarAngle = Math.PI - 0.2

    // The basemap is present-day coastline, not a historical reconstruction.
    const map = document.createElement('canvas')
    map.width = 2048
    map.height = 1024
    const ctx = map.getContext('2d')!
    ctx.fillStyle = '#bfd1cb'
    ctx.fillRect(0, 0, map.width, map.height)
    const topology = landData as unknown as LandTopology
    const land = feature(topology, topology.objects.land)
    ctx.fillStyle = '#617d6b'
    ctx.strokeStyle = '#e3e7d8'
    ctx.lineWidth = 1
    for (const landFeature of land.features) {
      if (landFeature.geometry.type !== 'MultiPolygon') continue
      for (const polygon of landFeature.geometry.coordinates) {
        ctx.beginPath()
        for (const ring of polygon) {
          ring.forEach(([lon, lat], i) => {
            const x = (lon + 180) / 360 * map.width
            const y = (90 - lat) / 180 * map.height
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
          })
          ctx.closePath()
        }
        ctx.fill('evenodd')
        ctx.stroke()
      }
    }
    const texture = new THREE.CanvasTexture(map)
    texture.colorSpace = THREE.SRGBColorSpace
    const geometry = new THREE.SphereGeometry(1.3, 64, 48)
    const material = new THREE.MeshBasicMaterial({ map: texture })
    const globe = new THREE.Mesh(geometry, material)
    // The initial angle is illustrative and is not a historical location.
    globe.rotation.y = -0.3
    scene.add(globe)
    const render = () => renderer.render(scene, camera)
    controls.addEventListener('change', render)
    const resize = () => {
      const width = container.clientWidth
      const height = container.clientHeight
      if (!width || !height) return
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
      render()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    turn.current = (direction) => { globe.rotation.y += direction * Math.PI / 8; render() }
    const contextLost = (event: Event) => { event.preventDefault(); setUnavailable(true) }
    renderer.domElement.addEventListener('webglcontextlost', contextLost)
    resize()
    return () => {
      turn.current = null
      observer.disconnect()
      controls.removeEventListener('change', render)
      controls.dispose()
      renderer.domElement.removeEventListener('webglcontextlost', contextLost)
      geometry.dispose()
      material.dispose()
      texture.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div className="globe-card">
    <div className="globe-copy"><p className="eyebrow">UNA MIRADA AL MUNDO</p><h2>La historia tiene un lugar.</h2><p>Gira el planeta para explorar el mundo actual. La cronología te permite descubrir los acontecimientos y consultar sus fuentes.</p><p className="globe-note">Mapa geográfico moderno y esquemático, basado en <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth</a>. No muestra fronteras históricas ni ubicaciones de los hitos, aún en revisión.</p><div className="globe-controls" aria-label="Controles del globo"><button type="button" onClick={() => turn.current?.(-1)} disabled={unavailable} aria-label="Girar globo a la izquierda">←</button><button type="button" onClick={() => turn.current?.(1)} disabled={unavailable} aria-label="Girar globo a la derecha">→</button><span>ARRASTRA O USA LOS CONTROLES</span></div></div>
    <div className="globe-stage">{unavailable && <p role="status" className="globe-fallback">El globo no está disponible en este dispositivo. Puedes explorar todos los acontecimientos en la cronología.</p>}<div className="globe-canvas" ref={host} aria-hidden="true" /></div>
  </div>
}
