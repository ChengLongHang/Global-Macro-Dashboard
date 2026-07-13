import * as THREE from 'three';

export function latLngToVector3(lat, lng, radius = 1.05) {
  const phi = (90 - lat) * Math.PI / 180;
  const theta = (lng + 180) * Math.PI / 180;
  
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

export function getCountryColor(countryId) {
  const colors = {
    'USA': '#ff6b6b',
    'GBR': '#ffd93d',
    'DEU': '#6bcbff',
    'JPN': '#ff6b9d',
    'CHN': '#ff9f43',
    'IND': '#a29bfe',
    'BRA': '#55efc4',
    'CAN': '#81ecec',
    'AUS': '#fdcb6e',
    'FRA': '#e17055',
    'ITA': '#fd79a8',
    'ESP': '#fdcb6e',
    'MEX': '#ff9f43',
    'KOR': '#a29bfe'
  };
  return colors[countryId] || '#6bcbff';
}