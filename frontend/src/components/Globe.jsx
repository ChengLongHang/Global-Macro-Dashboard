import React, { useRef, useState, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Sphere, Html, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { latLngToVector3, getCountryColor } from '../utils/geoUtils';

function CountryMarker({ country, onClick, selected, onHover }) {
  const [hovered, setHovered] = useState(false);
  const pos = latLngToVector3(country.lat, country.lng);
  
  return (
    <mesh
      position={pos}
      onClick={() => onClick(country)}
      onPointerOver={() => {
        setHovered(true);
        onHover(country);
      }}
      onPointerOut={() => {
        setHovered(false);
        onHover(null);
      }}
    >
      <sphereGeometry args={[0.04, 16, 16]} />
      <meshStandardMaterial
        color={selected ? '#ff6b6b' : hovered ? '#ffd93d' : getCountryColor(country.id)}
        emissive={selected || hovered ? '#ff6b6b' : 'black'}
        emissiveIntensity={selected ? 0.8 : 0.3}
      />
      {hovered && (
        <Html distanceFactor={12}>
          <div className="bg-black/90 text-white px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap border border-white/10 shadow-xl pointer-events-none">
            {country.name}
            <div className="text-[10px] text-gray-400 font-normal">Click to select</div>
          </div>
        </Html>
      )}
    </mesh>
  );
}

function Earth({ countries, onSelect, selectedCountry, onHover }) {
  const textureMap = useTexture('https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg');
  
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 3, 5]} intensity={1.5} />
      <directionalLight position={[-5, 0, -5]} intensity={0.5} />
      
      <Sphere args={[1, 64, 64]}>
        <meshStandardMaterial 
          map={textureMap} 
          roughness={0.3}
          metalness={0.1}
        />
      </Sphere>
      
      <Sphere args={[1.02, 64, 64]}>
        <meshPhongMaterial 
          transparent 
          opacity={0.08} 
          color="#4a9eff"
          side={THREE.BackSide}
        />
      </Sphere>
      
      {countries.map(country => (
        <CountryMarker
          key={country.id}
          country={country}
          onClick={onSelect}
          selected={selectedCountry?.id === country.id}
          onHover={onHover}
        />
      ))}
    </>
  );
}

export default function Globe({ onSelectCountry, selectedCountry, onHoverCountry }) {
  const [countries, setCountries] = useState([]);
  
  useEffect(() => {
    fetch('http://localhost:8000/api/countries')
      .then(res => res.json())
      .then(setCountries)
      .catch(console.error);
  }, []);
  
  return (
    <div className="w-full h-screen bg-gradient-to-b from-[#0a0a1a] to-[#1a1a3e]">
      <Canvas camera={{ position: [0, 0, 2.8], fov: 45 }}>
        <OrbitControls 
          enablePan={false}
          minDistance={1.8}
          maxDistance={4.5}
          rotateSpeed={0.6}
        />
        <Earth 
          countries={countries}
          onSelect={onSelectCountry}
          selectedCountry={selectedCountry}
          onHover={onHoverCountry}
        />
      </Canvas>
    </div>
  );
}