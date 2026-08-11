import * as THREE from 'three';

export function createStaticCharacterStarfield(count = 420) {
  const positions = new Float32Array(count * 3);
  let seed = 0x79f4a31;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0x100000000;
  };

  for (let index = 0; index < count; index += 1) {
    const radius = 720 + random() * 980;
    const azimuth = random() * Math.PI * 2;
    const polar = Math.acos(2 * random() - 1);
    positions[index * 3] = radius * Math.sin(polar) * Math.cos(azimuth);
    positions[index * 3 + 1] = radius * Math.sin(polar) * Math.sin(azimuth);
    positions[index * 3 + 2] = radius * Math.cos(polar);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: '#b9d6d7',
    depthWrite: false,
    opacity: 0.34,
    size: 2.2,
    sizeAttenuation: true,
    transparent: true,
  });
  const points = new THREE.Points(geometry, material);
  points.name = 'character-stage-static-starfield';
  points.renderOrder = -10;
  return points;
}

export function disposeStaticCharacterStarfield(points: THREE.Points) {
  points.geometry.dispose();
  const material = points.material;
  if (Array.isArray(material)) material.forEach((item) => item.dispose());
  else material.dispose();
}
