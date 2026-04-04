"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, Volume2, VolumeX, SkipBack, SkipForward } from "lucide-react";
import { cn, formatDuration } from "@/lib/utils";

interface AudioPlayerProps {
  src: string;
  duration?: number;
  transcription?: string;
  className?: string;
}

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export function AudioPlayer({ src, duration: initialDuration, transcription, className }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(initialDuration || 0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(2); // 1x default
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);
  const [waveformData, setWaveformData] = useState<number[]>([]);

  // Generate waveform visualization data
  useEffect(() => {
    const bars = 50;
    const data: number[] = [];
    // Generate pseudo-random waveform based on src hash
    let hash = 0;
    for (let i = 0; i < src.length; i++) {
      hash = src.charCodeAt(i) + ((hash << 5) - hash);
    }
    for (let i = 0; i < bars; i++) {
      const seed = Math.sin(hash * (i + 1)) * 10000;
      data.push(0.15 + Math.abs(seed - Math.floor(seed)) * 0.85);
    }
    setWaveformData(data);
  }, [src]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(() => setError(true));
    }
  }, [isPlaying]);

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
      setIsLoading(false);
    }
  }, []);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    const bar = progressRef.current;
    if (!audio || !bar) return;
    const rect = bar.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    audio.currentTime = pos * audio.duration;
  }, []);

  const handleSpeed = useCallback(() => {
    const next = (speedIndex + 1) % SPEEDS.length;
    setSpeedIndex(next);
    if (audioRef.current) {
      audioRef.current.playbackRate = SPEEDS[next];
    }
  }, [speedIndex]);

  const toggleMute = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  }, [isMuted]);

  const skip = useCallback((seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, Math.min(audioRef.current.currentTime + seconds, duration));
    }
  }, [duration]);

  const progress = duration > 0 ? currentTime / duration : 0;

  if (error) {
    return (
      <div className={cn("rounded-xl bg-dark-700/50 p-3 text-xs text-red-400", className)}>
        Erro ao carregar audio
      </div>
    );
  }

  return (
    <div className={cn("rounded-xl bg-dark-700/40 border border-dark-500/20 p-3 space-y-2", className)}>
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => { setIsPlaying(false); setCurrentTime(0); }}
        onError={() => setError(true)}
        onCanPlay={() => setIsLoading(false)}
      />

      {/* Waveform + Progress */}
      <div
        ref={progressRef}
        className="relative h-10 cursor-pointer group"
        onClick={handleSeek}
        role="slider"
        aria-label="Progresso do audio"
        aria-valuenow={Math.round(currentTime)}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        tabIndex={0}
      >
        <div className="flex items-end justify-center gap-[2px] h-full">
          {waveformData.map((height, i) => {
            const barProgress = i / waveformData.length;
            const isActive = barProgress <= progress;
            return (
              <div
                key={i}
                className={cn(
                  "w-[3px] rounded-full transition-colors duration-150",
                  isActive ? "bg-accent-400" : "bg-dark-500/60 group-hover:bg-dark-400/60"
                )}
                style={{ height: `${height * 100}%` }}
              />
            );
          })}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        {/* Skip back */}
        <button
          onClick={() => skip(-5)}
          className="p-1 rounded-lg text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Voltar 5 segundos"
        >
          <SkipBack className="w-3.5 h-3.5" />
        </button>

        {/* Play/Pause */}
        <button
          onClick={togglePlay}
          disabled={isLoading}
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center transition-all",
            isPlaying
              ? "bg-accent-400 text-dark-900 shadow-lg shadow-accent-400/30"
              : "bg-brand-500 text-white shadow-lg shadow-brand-500/30",
            isLoading && "opacity-50 cursor-not-allowed"
          )}
          aria-label={isPlaying ? "Pausar" : "Reproduzir"}
        >
          {isLoading ? (
            <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : isPlaying ? (
            <Pause className="w-3.5 h-3.5" />
          ) : (
            <Play className="w-3.5 h-3.5 ml-0.5" />
          )}
        </button>

        {/* Skip forward */}
        <button
          onClick={() => skip(5)}
          className="p-1 rounded-lg text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Avançar 5 segundos"
        >
          <SkipForward className="w-3.5 h-3.5" />
        </button>

        {/* Time */}
        <span className="text-[10px] text-gray-400 font-mono min-w-[70px]">
          {formatDuration(currentTime)} / {formatDuration(duration)}
        </span>

        {/* Speed */}
        <button
          onClick={handleSpeed}
          className="px-1.5 py-0.5 rounded text-[10px] font-mono text-gray-400 hover:text-white bg-dark-600/50 hover:bg-dark-500/50 transition-colors"
          aria-label={`Velocidade: ${SPEEDS[speedIndex]}x`}
        >
          {SPEEDS[speedIndex]}x
        </button>

        {/* Volume */}
        <button
          onClick={toggleMute}
          className="p-1 rounded-lg text-gray-500 hover:text-gray-300 transition-colors ml-auto"
          aria-label={isMuted ? "Ativar som" : "Desativar som"}
        >
          {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );
}
