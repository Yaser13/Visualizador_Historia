import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { feature } from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import landData from 'world-atlas/land-110m.json'
import { CategoryIcon, categoryMeta } from './icons'
import './Globe.css'

// Contract: docs/api/CONTRATO_CRONOLOGIAS.md §4. Coordinates are [longitude, latitude].
export type GlobeMarker = {
  id: string
  coordinates: [number, number]
  category: string
  label: string
  title: string
  dateLabel: string
  state: 'active' | 'past' | 'future'
}

type GlobeProps = { markers: GlobeMarker[]; activeId: string | null; onSelect?: (id: string) => void }
type MarkerState = GlobeMarker['state']
type LandTopology = Topology<{ land: GeometryCollection }>

// Markers closer than this (in degrees of arc) share one icon with a counter badge.
type Cluster = { key: string; coordinates: [number, number]; members: GlobeMarker[]; target: GlobeMarker; state: MarkerState }
type HoverInfo = { key: string; category: string; title: string; dateLabel: string; label: string; count: number }
type Entry = { cluster: Cluster; sprite: THREE.Sprite; material: THREE.SpriteMaterial; visibility: number }
type Tween = { fromDirection: THREE.Vector3; rotation: THREE.Quaternion; fromDistance: number; toDistance: number; start: number }
type Engine = {
  sync: (markers: GlobeMarker[], activeId: string | null) => void
  focus: (coordinates: [number, number] | null, markers: GlobeMarker[]) => void
  turn: (direction: number) => void
  zoom: (factor: number) => void
  dispose: () => void
}
type EngineOptions = {
  container: HTMLDivElement
  getLabel: () => HTMLDivElement | null
  getTooltip: () => HTMLDivElement | null
  onHover: (info: HoverInfo | null) => void
  onSelect: (id: string) => void
  onContextLost: () => void
}

const RADIUS = 1.3
const MARKER_RADIUS = RADIUS * 1.012
const CLUSTER_DEGREES = 0.3
// On-screen size of each icon quad in CSS pixels (constant at every zoom level).
const ICON_PX: Record<MarkerState, number> = { active: 54, past: 36, future: 26 }
const ICON_OPACITY: Record<MarkerState, number> = { active: 1, past: 0.85, future: 0.3 }
const RENDER_ORDER: Record<MarkerState, number> = { future: 10, past: 20, active: 40 }
const RING_RENDER_ORDER = 30
const HOVER_SCALE = 1.12
const TEXTURE_PX = 128
const FOCUS_DISTANCE = 2.7
const OVERVIEW_DISTANCE = 4.5
const CAMERA_MS = 700
const PULSE_MS = 1800
const CLICK_TOLERANCE_PX = 6

const isValidCoordinates = (value: unknown): value is [number, number] =>
  Array.isArray(value) && value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])
  && Math.abs(value[0]) <= 180 && Math.abs(value[1]) <= 90

const findActive = (markers: GlobeMarker[], activeId: string | null) =>
  markers.find((marker) => (activeId !== null ? marker.id === activeId : marker.state === 'active') && isValidCoordinates(marker.coordinates)) ?? null

const memberState = (marker: GlobeMarker, activeId: string | null): MarkerState => {
  const active = activeId !== null ? marker.id === activeId : marker.state === 'active'
  if (active) return 'active'
  return marker.state === 'future' ? 'future' : 'past'
}

const arcDegrees = ([lon1, lat1]: [number, number], [lon2, lat2]: [number, number]) => {
  const toRad = THREE.MathUtils.degToRad
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return THREE.MathUtils.radToDeg(2 * Math.asin(Math.min(1, Math.sqrt(a))))
}

function clusterMarkers(markers: GlobeMarker[], activeId: string | null): Cluster[] {
  const groups: { coordinates: [number, number]; members: GlobeMarker[] }[] = []
  for (const marker of markers) {
    if (!isValidCoordinates(marker.coordinates)) continue
    const group = groups.find((candidate) => arcDegrees(candidate.coordinates, marker.coordinates) < CLUSTER_DEGREES)
    if (group) group.members.push(marker)
    else groups.push({ coordinates: [marker.coordinates[0], marker.coordinates[1]], members: [marker] })
  }
  return groups.map(({ coordinates, members }) => {
    const states = members.map((marker) => memberState(marker, activeId))
    const activeIndex = states.indexOf('active')
    // Click target: the active member, otherwise the most recent one (last in the array).
    const target = activeIndex >= 0 ? members[activeIndex] : members[members.length - 1]
    const state: MarkerState = activeIndex >= 0 ? 'active' : states.includes('past') ? 'past' : 'future'
    return { key: members.map((marker) => marker.id).join('|'), coordinates, members, target, state }
  })
}

const surfaceNormal = ([longitude, latitude]: [number, number]) => {
  const lon = THREE.MathUtils.degToRad(longitude)
  const lat = THREE.MathUtils.degToRad(latitude)
  return new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.sin(lat), -Math.cos(lat) * Math.sin(lon))
}

const smoothstep = (edge0: number, edge1: number, x: number) => {
  const t = THREE.MathUtils.clamp((x - edge0) / (edge1 - edge0), 0, 1)
  return t * t * (3 - 2 * t)
}

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2)

const shorten = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text)

function createBaseMapTexture() {
  // The basemap is present-day coastline, not a political or historical map.
  const map = document.createElement('canvas')
  map.width = 2048
  map.height = 1024
  const ctx = map.getContext('2d')
  if (ctx) {
    ctx.fillStyle = '#3b5960'
    ctx.fillRect(0, 0, map.width, map.height)
    const topology = landData as unknown as LandTopology
    const land = feature(topology, topology.objects.land)
    ctx.fillStyle = '#79836b'
    ctx.strokeStyle = '#a7b19a'
    ctx.lineWidth = 1.5
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
    // Geographic graticule, not terrain or borders.
    ctx.strokeStyle = 'rgba(228, 221, 187, 0.12)'
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let longitude = -150; longitude <= 150; longitude += 30) {
      const x = (longitude + 180) / 360 * map.width
      ctx.moveTo(x, 0); ctx.lineTo(x, map.height)
    }
    for (let latitude = -60; latitude <= 60; latitude += 30) {
      const y = (90 - latitude) / 180 * map.height
      ctx.moveTo(0, y); ctx.lineTo(map.width, y)
    }
    ctx.stroke()
  }
  const texture = new THREE.CanvasTexture(map)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

// Category icon: dark disc, category-coloured border and glyph, optional counter badge.
function createIconTexture(category: string, badge: string) {
  const meta = categoryMeta(category)
  const canvas = document.createElement('canvas')
  canvas.width = TEXTURE_PX
  canvas.height = TEXTURE_PX
  const ctx = canvas.getContext('2d')
  if (ctx) {
    const c = TEXTURE_PX / 2
    const r = 44
    ctx.beginPath(); ctx.arc(c, c + 3, r + 5, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(6, 12, 13, 0.45)'; ctx.fill()
    ctx.beginPath(); ctx.arc(c, c, r, 0, Math.PI * 2)
    ctx.fillStyle = '#192827'; ctx.fill()
    ctx.lineWidth = 6; ctx.strokeStyle = meta.color; ctx.stroke()
    ctx.beginPath(); ctx.arc(c, c, r + 3.5, 0, Math.PI * 2)
    ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(8, 14, 15, 0.9)'; ctx.stroke()
    const scale = 2.15
    ctx.save()
    ctx.translate(c - 12 * scale, c - 12 * scale)
    ctx.scale(scale, scale)
    ctx.strokeStyle = meta.color
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.stroke(new Path2D(meta.path))
    ctx.restore()
    if (badge) {
      const bx = 104
      const by = 24
      const br = badge.length > 2 ? 22 : 19
      ctx.beginPath(); ctx.arc(bx, by, br, 0, Math.PI * 2)
      ctx.fillStyle = '#d7a964'; ctx.fill()
      ctx.lineWidth = 3; ctx.strokeStyle = '#192827'; ctx.stroke()
      ctx.fillStyle = '#192827'
      ctx.font = `800 ${badge.length > 2 ? 16 : badge.length > 1 ? 20 : 24}px system-ui, -apple-system, "Segoe UI", sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(badge, bx, by + 1)
    }
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function createRingTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = TEXTURE_PX
  canvas.height = TEXTURE_PX
  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.beginPath(); ctx.arc(TEXTURE_PX / 2, TEXTURE_PX / 2, 57, 0, Math.PI * 2)
    ctx.lineWidth = 5; ctx.strokeStyle = '#ffffff'; ctx.stroke()
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function createGlobeEngine(options: EngineOptions): Engine | null {
  const { container } = options
  let renderer: THREE.WebGLRenderer
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  } catch {
    return null
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  const canvas = renderer.domElement
  container.appendChild(canvas)
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100)
  camera.position.set(0, 0, OVERVIEW_DISTANCE)
  const controls = new OrbitControls(camera, canvas)
  controls.enablePan = false
  controls.enableZoom = true
  controls.minDistance = 1.8
  controls.maxDistance = 6
  controls.enableDamping = false
  controls.rotateSpeed = 0.6
  controls.minPolarAngle = 0.2
  controls.maxPolarAngle = Math.PI - 0.2

  const baseTexture = createBaseMapTexture()
  const globeGeometry = new THREE.SphereGeometry(RADIUS, 64, 48)
  const globeMaterial = new THREE.MeshBasicMaterial({ map: baseTexture })
  const globe = new THREE.Mesh(globeGeometry, globeMaterial)
  // The initial angle is illustrative.
  globe.rotation.y = -0.3
  scene.add(globe)
  const markerLayer = new THREE.Group()
  globe.add(markerLayer)

  const iconTextures = new Map<string, THREE.CanvasTexture>()
  const iconTexture = (category: string, count: number) => {
    const badge = count > 1 ? (count > 99 ? '99+' : String(count)) : ''
    const key = `${categoryMeta(category).key}|${badge}`
    let texture = iconTextures.get(key)
    if (!texture) {
      texture = createIconTexture(category, badge)
      iconTextures.set(key, texture)
    }
    return texture
  }

  const ringTexture = createRingTexture()
  const ringMaterial = new THREE.SpriteMaterial({ map: ringTexture, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: false })
  const ring = new THREE.Sprite(ringMaterial)
  ring.renderOrder = RING_RENDER_ORDER
  ring.visible = false
  markerLayer.add(ring)

  const entries = new Map<string, Entry>()
  let hoveredKey: string | null = null
  // Last mouse position over the canvas, used to refresh the hover when the camera or markers move.
  let hoverPointer: { x: number; y: number } | null = null
  let hoverDirty = false
  let press: { id: number; x: number; y: number; moved: boolean } | null = null
  let unitPerPx = 0
  let tween: Tween | null = null
  let hasFocused = false
  let frameId = 0
  let inFrame = false
  let disposed = false

  const motionQuery = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
  let reducedMotion = motionQuery?.matches ?? false

  const worldPosition = new THREE.Vector3()
  const toCamera = new THREE.Vector3()
  const projected = new THREE.Vector3()
  const slerped = new THREE.Quaternion()
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()

  const applyScale = (entry: Entry) => {
    const px = ICON_PX[entry.cluster.state] * (entry.cluster.key === hoveredKey ? HOVER_SCALE : 1)
    entry.sprite.scale.set(px * unitPerPx, px * unitPerPx, 1)
  }

  // Projects a world-space point to the container; returns null if off-screen.
  const toScreen = (sprite: THREE.Sprite) => {
    sprite.getWorldPosition(projected).project(camera)
    if (projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) return null
    return { x: projected.x, y: projected.y }
  }

  const updateVisibility = () => {
    scene.updateMatrixWorld()
    camera.updateMatrixWorld()
    let activeEntry: Entry | null = null
    for (const entry of entries.values()) {
      entry.sprite.getWorldPosition(worldPosition)
      toCamera.copy(camera.position).sub(worldPosition).normalize()
      // Hide icons on the far hemisphere and fade them near the limb so they never show through the globe.
      const facing = worldPosition.normalize().dot(toCamera)
      entry.visibility = smoothstep(0.02, 0.2, facing)
      entry.sprite.visible = entry.visibility > 0.01
      entry.material.opacity = ICON_OPACITY[entry.cluster.state] * entry.visibility
      if (entry.cluster.state === 'active') activeEntry = entry
    }
    return activeEntry
  }

  const render = (now: number) => {
    const activeEntry = updateVisibility()
    let pulsing = false
    if (activeEntry && activeEntry.sprite.visible) {
      ring.visible = true
      ring.position.copy(activeEntry.sprite.position)
      const base = ICON_PX.active * unitPerPx
      if (reducedMotion || !onScreen) {
        ring.scale.set(base * 1.35, base * 1.35, 1)
        ringMaterial.opacity = 0.55 * activeEntry.visibility
      } else {
        const t = (now % PULSE_MS) / PULSE_MS
        const size = base * (1 + 0.8 * t)
        ring.scale.set(size, size, 1)
        ringMaterial.opacity = 0.8 * (1 - t) * activeEntry.visibility
        pulsing = true
      }
    } else {
      ring.visible = false
    }

    const label = options.getLabel()
    if (label) {
      const point = activeEntry && activeEntry.visibility > 0.35 ? toScreen(activeEntry.sprite) : null
      label.style.display = point ? '' : 'none'
      if (point) {
        // Place the label beside the icon where it fits; otherwise centre it below (narrow screens).
        const stageWidth = container.clientWidth
        const x = (point.x + 1) / 2 * stageWidth
        const width = label.offsetWidth
        const gap = ICON_PX.active / 2 + 8
        const side = x + gap + width <= stageWidth - 8 ? 'right' : x - gap - width >= 8 ? 'left' : 'below'
        const left = side === 'below' ? THREE.MathUtils.clamp(x, width / 2 + 8, Math.max(width / 2 + 8, stageWidth - width / 2 - 8)) : x
        label.style.left = `${left}px`
        label.style.top = `${(1 - point.y) * 50}%`
        label.dataset.side = side
      }
    }

    const tooltip = options.getTooltip()
    if (tooltip) {
      const hovered = hoveredKey ? entries.get(hoveredKey) : undefined
      // A single active icon already has its label; the tooltip would only duplicate it.
      const redundant = hovered?.cluster.state === 'active' && hovered.cluster.members.length === 1
      const point = hovered && !redundant && hovered.visibility > 0.35 ? toScreen(hovered.sprite) : null
      tooltip.style.display = point ? '' : 'none'
      if (point) {
        tooltip.style.left = `${(point.x + 1) * 50}%`
        tooltip.style.top = `${(1 - point.y) * 50}%`
        tooltip.dataset.side = point.y > 0.7 ? 'below' : 'above'
      }
    }

    renderer.render(scene, camera)
    return pulsing
  }

  const frame = (now: number) => {
    frameId = 0
    if (disposed) return
    inFrame = true
    let animating = false
    if (tween) {
      const t = Math.min(1, (now - tween.start) / CAMERA_MS)
      const eased = easeInOutCubic(t)
      slerped.identity().slerp(tween.rotation, eased)
      camera.position.copy(tween.fromDirection).applyQuaternion(slerped)
        .multiplyScalar(THREE.MathUtils.lerp(tween.fromDistance, tween.toDistance, eased))
      controls.update()
      if (t < 1) animating = true
      else tween = null
      hoverDirty = true
    }
    if (hoverDirty) {
      hoverDirty = false
      if (hoverPointer && !press) {
        updateVisibility()
        setHovered(pick(hoverPointer.x, hoverPointer.y))
      }
    }
    const pulsing = render(now)
    inFrame = false
    // Keep requesting frames only while the camera moves or the active ring pulses.
    if (animating || pulsing) frameId = requestAnimationFrame(frame)
  }

  const invalidate = () => {
    if (disposed || inFrame || frameId) return
    frameId = requestAnimationFrame(frame)
  }

  // Camera, globe or markers changed: re-check what is under the mouse on the next frame.
  const markHoverDirty = () => {
    hoverDirty = true
    invalidate()
  }

  const renderNow = () => {
    if (frameId) cancelAnimationFrame(frameId)
    frameId = 0
    frame(performance.now())
  }

  const hoverInfo = (cluster: Cluster): HoverInfo => ({
    key: cluster.key,
    category: cluster.target.category,
    title: cluster.target.title,
    dateLabel: cluster.target.dateLabel,
    label: cluster.target.label,
    count: cluster.members.length,
  })

  const setHovered = (entry: Entry | null) => {
    const key = entry?.cluster.key ?? null
    if (key === hoveredKey) return
    const previous = hoveredKey ? entries.get(hoveredKey) : undefined
    hoveredKey = key
    if (previous) applyScale(previous)
    if (entry) applyScale(entry)
    canvas.style.cursor = entry ? 'pointer' : ''
    options.onHover(entry ? hoverInfo(entry.cluster) : null)
    invalidate()
  }

  const pick = (clientX: number, clientY: number): Entry | null => {
    const rect = canvas.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    pointer.set((clientX - rect.left) / rect.width * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1)
    const candidates = [...entries.values()].filter((entry) => entry.sprite.visible && entry.visibility > 0.35)
    if (!candidates.length) return null
    scene.updateMatrixWorld()
    camera.updateMatrixWorld()
    raycaster.setFromCamera(pointer, camera)
    const hits = raycaster.intersectObjects(candidates.map((entry) => entry.sprite), false)
    if (!hits.length) return null
    // Icons are drawn without depth test; prefer the most prominent one (active > past > future).
    hits.sort((a, b) => b.object.renderOrder - a.object.renderOrder || a.distance - b.distance)
    return candidates.find((entry) => entry.sprite === hits[0].object) ?? null
  }

  const onPointerDown = (event: PointerEvent) => {
    press = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false }
  }
  const onPointerMove = (event: PointerEvent) => {
    if (press && press.id === event.pointerId) {
      if (Math.hypot(event.clientX - press.x, event.clientY - press.y) > CLICK_TOLERANCE_PX) {
        press.moved = true
        setHovered(null)
      }
      return
    }
    if (event.pointerType === 'touch') return
    hoverPointer = { x: event.clientX, y: event.clientY }
    setHovered(pick(event.clientX, event.clientY))
  }
  const onPointerUp = (event: PointerEvent) => {
    if (!press || press.id !== event.pointerId) return
    const wasDrag = press.moved || Math.hypot(event.clientX - press.x, event.clientY - press.y) > CLICK_TOLERANCE_PX
    press = null
    if (event.pointerType !== 'touch') { hoverPointer = { x: event.clientX, y: event.clientY }; markHoverDirty() }
    if (wasDrag) return
    const hit = pick(event.clientX, event.clientY)
    if (hit) options.onSelect(hit.cluster.target.id)
  }
  const onPointerCancel = () => { press = null }
  const onPointerLeave = () => {
    hoverPointer = null
    if (!press) setHovered(null)
  }
  canvas.addEventListener('pointerdown', onPointerDown)
  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('pointerup', onPointerUp)
  canvas.addEventListener('pointercancel', onPointerCancel)
  canvas.addEventListener('pointerleave', onPointerLeave)

  const onControlsStart = () => { tween = null }
  controls.addEventListener('change', markHoverDirty)
  controls.addEventListener('start', onControlsStart)

  const onMotionChange = (event: MediaQueryListEvent) => {
    reducedMotion = event.matches
    if (reducedMotion) tween = null
    invalidate()
  }
  motionQuery?.addEventListener('change', onMotionChange)

  const resize = () => {
    const width = container.clientWidth
    const height = container.clientHeight
    if (!width || !height) return
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    renderer.setSize(width, height)
    // Sprites use sizeAttenuation=false: scale is in view units at distance 1.
    unitPerPx = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / height
    for (const entry of entries.values()) applyScale(entry)
    renderNow()
  }
  const observer = new ResizeObserver(resize)
  observer.observe(container)
  // Stop the pulse loop while the globe is scrolled out of view.
  let onScreen = true
  const visibilityObserver = typeof IntersectionObserver === 'function'
    ? new IntersectionObserver(([record]) => { onScreen = record?.isIntersecting ?? true; invalidate() })
    : null
  visibilityObserver?.observe(container)

  const onContextLost = (event: Event) => {
    event.preventDefault()
    if (frameId) cancelAnimationFrame(frameId)
    frameId = 0
    tween = null
    options.onContextLost()
  }
  canvas.addEventListener('webglcontextlost', onContextLost)
  resize()

  const removeEntry = (key: string, entry: Entry) => {
    markerLayer.remove(entry.sprite)
    entry.material.dispose()
    entries.delete(key)
  }

  return {
    sync(markers, activeId) {
      const clusters = clusterMarkers(markers, activeId)
      const keys = new Set<string>()
      for (const cluster of clusters) {
        keys.add(cluster.key)
        const map = iconTexture(cluster.target.category, cluster.members.length)
        let entry = entries.get(cluster.key)
        if (!entry) {
          const material = new THREE.SpriteMaterial({ map, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: false })
          const sprite = new THREE.Sprite(material)
          markerLayer.add(sprite)
          entry = { cluster, sprite, material, visibility: 0 }
          entries.set(cluster.key, entry)
        }
        entry.cluster = cluster
        entry.sprite.position.copy(surfaceNormal(cluster.coordinates)).multiplyScalar(MARKER_RADIUS)
        entry.sprite.renderOrder = RENDER_ORDER[cluster.state]
        entry.material.map = map
        applyScale(entry)
        if (cluster.state === 'active') ringMaterial.color.set(categoryMeta(cluster.target.category).color)
      }
      for (const [key, entry] of entries) if (!keys.has(key)) removeEntry(key, entry)
      if (hoveredKey) {
        const hovered = entries.get(hoveredKey)
        if (hovered) options.onHover(hoverInfo(hovered.cluster))
        else { hoveredKey = null; canvas.style.cursor = ''; options.onHover(null) }
      }
      markHoverDirty()
    },
    focus(coordinates, markers) {
      const currentDistance = camera.position.length()
      let direction: THREE.Vector3
      let distance: number
      if (coordinates) {
        direction = surfaceNormal(coordinates).applyQuaternion(globe.quaternion)
        distance = Math.min(currentDistance, FOCUS_DISTANCE)
      } else {
        // General view: centre on the located markers (if any) without zooming in.
        const sum = new THREE.Vector3()
        for (const marker of markers) if (isValidCoordinates(marker.coordinates)) sum.add(surfaceNormal(marker.coordinates))
        direction = sum.lengthSq() > 1e-6 ? sum.normalize().applyQuaternion(globe.quaternion) : camera.position.clone().normalize()
        distance = Math.max(currentDistance, OVERVIEW_DISTANCE)
      }
      distance = THREE.MathUtils.clamp(distance, controls.minDistance, controls.maxDistance)
      const fromDirection = camera.position.clone().normalize()
      const animate = hasFocused && !reducedMotion
      hasFocused = true
      if (!animate || (fromDirection.angleTo(direction) < 1e-3 && Math.abs(currentDistance - distance) < 1e-3)) {
        tween = null
        camera.position.copy(direction).multiplyScalar(distance)
        controls.update()
        markHoverDirty()
        return
      }
      tween = {
        fromDirection,
        rotation: new THREE.Quaternion().setFromUnitVectors(fromDirection, direction),
        fromDistance: currentDistance,
        toDistance: distance,
        start: performance.now(),
      }
      invalidate()
    },
    turn(direction) {
      tween = null
      globe.rotation.y += direction * Math.PI / 8
      markHoverDirty()
    },
    zoom(factor) {
      tween = null
      const distance = THREE.MathUtils.clamp(camera.position.length() * factor, controls.minDistance, controls.maxDistance)
      camera.position.setLength(distance)
      controls.update()
      markHoverDirty()
    },
    dispose() {
      disposed = true
      if (frameId) cancelAnimationFrame(frameId)
      frameId = 0
      observer.disconnect()
      visibilityObserver?.disconnect()
      motionQuery?.removeEventListener('change', onMotionChange)
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerCancel)
      canvas.removeEventListener('pointerleave', onPointerLeave)
      canvas.removeEventListener('webglcontextlost', onContextLost)
      controls.removeEventListener('change', markHoverDirty)
      controls.removeEventListener('start', onControlsStart)
      controls.dispose()
      for (const [key, entry] of entries) removeEntry(key, entry)
      for (const texture of iconTextures.values()) texture.dispose()
      iconTextures.clear()
      markerLayer.remove(ring)
      ringMaterial.dispose()
      ringTexture.dispose()
      globeGeometry.dispose()
      globeMaterial.dispose()
      baseTexture.dispose()
      renderer.dispose()
      canvas.remove()
    },
  }
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

export default function Globe({ markers, activeId, onSelect }: GlobeProps) {
  const host = useRef<HTMLDivElement>(null)
  const labelRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const engine = useRef<Engine | null>(null)
  const latest = useRef({ markers, activeId, onSelect })
  const [unavailable, setUnavailable] = useState(false)
  const [hover, setHover] = useState<HoverInfo | null>(null)

  // Declared first so the effects below always read the current props.
  useEffect(() => { latest.current = { markers, activeId, onSelect } })

  useEffect(() => {
    const container = host.current
    if (!container) return
    const instance = createGlobeEngine({
      container,
      getLabel: () => labelRef.current,
      getTooltip: () => tooltipRef.current,
      onHover: setHover,
      onSelect: (id) => latest.current.onSelect?.(id),
      onContextLost: () => setUnavailable(true),
    })
    if (!instance) {
      setUnavailable(true)
      return
    }
    engine.current = instance
    return () => {
      engine.current = null
      instance.dispose()
    }
  }, [])

  // Prop updates only add, remove or update sprites; the renderer is created once.
  useEffect(() => { engine.current?.sync(markers, activeId) }, [markers, activeId])

  const active = useMemo(() => findActive(markers, activeId), [markers, activeId])
  const focusKey = active ? `${active.id}@${active.coordinates[0]},${active.coordinates[1]}` : 'overview'
  useEffect(() => {
    const current = latest.current
    engine.current?.focus(findActive(current.markers, current.activeId)?.coordinates ?? null, current.markers)
  }, [focusKey])

  const { located, places } = useMemo(() => ({
    located: markers.filter((marker) => isValidCoordinates(marker.coordinates)).length,
    places: clusterMarkers(markers, null).length,
  }), [markers])
  const countText = located === 0
    ? 'ningún hito ubicado en el globo'
    : `${plural(located, 'hito ubicado', 'hitos ubicados')} en el globo${places < located ? ` (${plural(places, 'lugar', 'lugares')})` : ''}`
  const note = active
    ? `${active.label}: referencia aproximada · ${countText}`
    : activeId !== null
      ? `Vista general; el hito seleccionado no tiene ubicación puntual · ${countText}`
      : `Vista general · ${countText}`

  return <div className="globe-card">
    <div className="globe-copy">
      <p className="globe-note" aria-live="polite">{note}</p>
      <p className="globe-note">Iconos = tipo de acontecimiento en una ubicación aproximada; no indican fuerzas, rutas ni control territorial. Mapa base de <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">Natural Earth</a>; las costas no representan límites políticos.</p>
      <div className="globe-controls" aria-label="Controles del globo">
        <button type="button" onClick={() => engine.current?.turn(-1)} disabled={unavailable} aria-label="Girar globo a la izquierda">←</button>
        <button type="button" onClick={() => engine.current?.turn(1)} disabled={unavailable} aria-label="Girar globo a la derecha">→</button>
        <button type="button" onClick={() => engine.current?.zoom(0.8)} disabled={unavailable} aria-label="Acercar globo">+</button>
        <button type="button" onClick={() => engine.current?.zoom(1.25)} disabled={unavailable} aria-label="Alejar globo">−</button>
        <span>ARRASTRA PARA EXPLORAR</span>
      </div>
    </div>
    <div className="globe-stage">
      {unavailable && <p role="status" className="globe-fallback">El globo no está disponible en este dispositivo. Puedes explorar todos los acontecimientos en la cronología.</p>}
      <div className="globe-canvas" ref={host} aria-hidden="true" />
      <div className="globe-location-label globe-active-label" ref={labelRef} aria-hidden="true" style={{ display: 'none' }}>
        {active && <>
          <span className="globe-active-icon"><CategoryIcon category={active.category} size={16} /></span>
          <span className="globe-active-text">
            <span className="globe-active-place">{active.label} <small>APROX.</small></span>
            <span className="globe-active-title">{shorten(active.title, 64)}</span>
            <span className="globe-active-date">{active.dateLabel}</span>
          </span>
        </>}
      </div>
      <div className="globe-tooltip" ref={tooltipRef} aria-hidden="true" style={{ display: 'none' }}>
        {hover && <>
          <strong>{shorten(hover.title, 90)}</strong>
          <span className="globe-tooltip-meta"><CategoryIcon category={hover.category} size={12} /> {hover.dateLabel} · {hover.label}</span>
          {hover.count > 1 && <span className="globe-tooltip-more">{plural(hover.count, 'hito', 'hitos')} en este lugar; al pulsar se abre el seleccionado o el más reciente</span>}
        </>}
      </div>
    </div>
  </div>
}
