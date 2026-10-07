import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { createScene } from './data/object.js';
import fs from 'fs';

const root = createScene();
root.updateMatrixWorld(true);

const geometries = [];

root.traverse((obj) => {
  if (obj.isInstancedMesh) {
    const instanceMatrix = new THREE.Matrix4();
    const worldMatrix = new THREE.Matrix4();
    for (let i = 0; i < obj.count; i++) {
      obj.getMatrixAt(i, instanceMatrix);
      worldMatrix.copy(obj.matrixWorld).multiply(instanceMatrix);
      let geom = obj.geometry.clone();
      geom.applyMatrix4(worldMatrix);
      if (geom.index) geom = geom.toNonIndexed();
      if (!geom.attributes.normal) geom.computeVertexNormals();
      geometries.push(geom);
    }
  } else if (obj.isMesh) {
    let geom = obj.geometry.clone();
    geom.applyMatrix4(obj.matrixWorld);
    if (geom.index) geom = geom.toNonIndexed();
    if (!geom.attributes.normal) geom.computeVertexNormals();
    geometries.push(geom);
  }
});

// Keep only common attributes across geometries to allow merging
const commonAttrs = ['position', 'normal'];
const trimmed = geometries.map((g) => {
  const ng = new THREE.BufferGeometry();
  for (const name of commonAttrs) {
    if (g.attributes[name]) ng.setAttribute(name, g.attributes[name]);
  }
  return ng;
});

const merged = mergeGeometries(trimmed, false);
if (!merged) throw new Error('Failed to merge geometries');

// Convert Y-up (Three.js) to Z-up (Blender) by rotating -90° around X
const axisMatrix = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
merged.applyMatrix4(axisMatrix);

const exportMesh = new THREE.Mesh(merged);
const objData = new OBJExporter().parse(exportMesh);

fs.writeFileSync('/root/output/object.obj', objData);
console.log('Wrote /root/output/object.obj');
console.log('Vertex count:', merged.attributes.position.count);
