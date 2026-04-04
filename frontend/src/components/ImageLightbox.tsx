"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, ZoomIn, ZoomOut, RotateCw, Download, ChevronLeft, ChevronRight,
  Maximize, Info
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { MediaMetadata } from "@/types";

interface LightboxImage {
  src: string;
  alt: string;
  filename?: string;
  metadata?: MediaMetadata;
  description?: string;
  ocrText?: string;
}

interface ImageLightboxProps {
  images: LightboxImage[];
  initialIndex: number;
  isOpen: boolean;
  onClose: () => void;
}

export function ImageLightbox({ images, initialIndex, isOpen, onClose }: ImageLightboxProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [showInfo, setShowInfo] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrentIndex(initialIndex);
  }, [initialIndex]);

  // Reset zoom/rotation on image change
  useEffect(() => {
    setZoom(1);
    setRotation(0);
    setOffset({ x: 0, y: 0 });
  }, [currentIndex]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      switch (e.key) {
        case "Escape":
          onClose();
          break;
        case "ArrowLeft":
          setCurrentIndex((i) => (i > 0 ? i - 1 : images.length - 1));
          break;
        case "ArrowRight":
          setCurrentIndex((i) => (i < images.length - 1 ? i + 1 : 0));
          break;
        case "+":
        case "=":
          setZoom((z) => Math.min(z + 0.5, 5));
          break;
        case "-":
          setZoom((z) => Math.max(z - 0.5, 0.5));
          break;
        case "r":
          setRotation((r) => r + 90);
          break;
        case "i":
          setShowInfo((s) => !s);
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, images.length, onClose]);

  // Mouse wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.max(0.5, Math.min(5, z - e.deltaY * 0.001)));
  }, []);

  // Drag to pan
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  }, [zoom, offset]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const current = images[currentIndex];
  if (!current) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] bg-black/95 flex"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          {/* Toolbar */}
          <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-black/60 to-transparent">
            <div className="text-sm text-white/80">
              {current.filename && (
                <span className="font-medium">{current.filename}</span>
              )}
              <span className="ml-3 text-white/50">
                {currentIndex + 1} / {images.length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setZoom((z) => Math.min(z + 0.5, 5))}
                className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Zoom in"
              >
                <ZoomIn className="w-5 h-5" />
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(z - 0.5, 0.5))}
                className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Zoom out"
              >
                <ZoomOut className="w-5 h-5" />
              </button>
              <button
                onClick={() => setRotation((r) => r + 90)}
                className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Rotacionar"
              >
                <RotateCw className="w-5 h-5" />
              </button>
              <button
                onClick={() => setShowInfo(!showInfo)}
                className={cn(
                  "p-2 rounded-lg transition-colors",
                  showInfo ? "text-accent-400 bg-white/10" : "text-white/70 hover:text-white hover:bg-white/10"
                )}
                aria-label="Informacoes"
              >
                <Info className="w-5 h-5" />
              </button>
              <a
                href={current.src}
                download={current.filename}
                className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Download"
              >
                <Download className="w-5 h-5" />
              </a>
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Fechar"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Navigation arrows */}
          {images.length > 1 && (
            <>
              <button
                onClick={() => setCurrentIndex((i) => (i > 0 ? i - 1 : images.length - 1))}
                className="absolute left-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full bg-black/50 hover:bg-black/70 text-white flex items-center justify-center transition-colors"
                aria-label="Imagem anterior"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
              <button
                onClick={() => setCurrentIndex((i) => (i < images.length - 1 ? i + 1 : 0))}
                className="absolute right-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full bg-black/50 hover:bg-black/70 text-white flex items-center justify-center transition-colors"
                aria-label="Proxima imagem"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            </>
          )}

          {/* Image */}
          <div
            ref={containerRef}
            className={cn(
              "flex-1 flex items-center justify-center overflow-hidden",
              zoom > 1 ? "cursor-grab" : "cursor-default",
              isDragging && "cursor-grabbing"
            )}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <motion.img
              key={currentIndex}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              src={current.src}
              alt={current.alt}
              className="max-w-[90vw] max-h-[85vh] object-contain select-none"
              style={{
                transform: `scale(${zoom}) rotate(${rotation}deg) translate(${offset.x / zoom}px, ${offset.y / zoom}px)`,
                transition: isDragging ? "none" : "transform 0.2s ease",
              }}
              draggable={false}
            />
          </div>

          {/* Thumbnail strip */}
          {images.length > 1 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 bg-black/60 rounded-xl p-2 max-w-[80vw] overflow-x-auto">
              {images.map((img, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentIndex(i)}
                  className={cn(
                    "w-12 h-12 rounded-lg overflow-hidden border-2 transition-all flex-shrink-0",
                    i === currentIndex ? "border-accent-400 opacity-100" : "border-transparent opacity-50 hover:opacity-80"
                  )}
                >
                  <img
                    src={img.src}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </button>
              ))}
            </div>
          )}

          {/* Info panel */}
          <AnimatePresence>
            {showInfo && (
              <motion.div
                initial={{ x: 400, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: 400, opacity: 0 }}
                className="absolute right-0 top-0 bottom-0 w-[320px] bg-dark-800/95 backdrop-blur-xl border-l border-dark-500/30 overflow-y-auto p-5 z-20"
              >
                <h3 className="font-semibold text-white mb-4">Detalhes da Imagem</h3>
                <div className="space-y-3">
                  {current.filename && (
                    <InfoRow label="Arquivo" value={current.filename} />
                  )}
                  {current.metadata?.resolution && (
                    <InfoRow label="Resolucao" value={current.metadata.resolution} />
                  )}
                  {current.metadata?.file_size_formatted && (
                    <InfoRow label="Tamanho" value={current.metadata.file_size_formatted} />
                  )}
                  {current.metadata?.format && (
                    <InfoRow label="Formato" value={current.metadata.format.toUpperCase()} />
                  )}
                  {current.metadata?.codec && (
                    <InfoRow label="Codec" value={current.metadata.codec} />
                  )}
                  {current.description && (
                    <div className="mt-4">
                      <p className="text-[10px] text-brand-400 font-medium mb-1">DESCRICAO IA</p>
                      <p className="text-xs text-gray-300 leading-relaxed">{current.description}</p>
                    </div>
                  )}
                  {current.ocrText && (
                    <div className="mt-4">
                      <p className="text-[10px] text-yellow-400 font-medium mb-1">TEXTO (OCR)</p>
                      <p className="text-xs text-gray-300 leading-relaxed font-mono">{current.ocrText}</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-gray-500 uppercase">{label}</p>
      <p className="text-sm text-gray-200">{value}</p>
    </div>
  );
}
