import type { ArtifactDeckPose } from './artifactDeckLayout';

export function artifactDeckPoseVars(pose: ArtifactDeckPose) {
  return {
    autoAlpha: pose.opacity,
    force3D: true,
    rotationX: pose.rotationX,
    rotationY: pose.rotationY,
    rotationZ: pose.rotationZ,
    scale: pose.scale,
    transformOrigin: '50% 50%',
    x: pose.x,
    xPercent: -50,
    y: pose.y,
    yPercent: -50,
    z: pose.z,
  };
}
