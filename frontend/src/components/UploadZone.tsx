"use client";

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Zap, FileArchive, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  onUpload: (file: File) => void;
  isUploading?: boolean;
}

export function UploadZone({ onUpload, isUploading = false }: UploadZoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      setError(null);

      if (rejectedFiles.length > 0) {
        const rejection = rejectedFiles[0];
        setUploadedFile(null);
        if (rejection.errors[0]?.code === "file-too-large") {
          setError("Arquivo muito grande. Máximo: 500MB");
        } else if (rejection.errors[0]?.code === "file-invalid-type") {
          setError("Apenas arquivos .zip são aceitos");
        } else {
          setError("Arquivo inválido");
        }
        return;
      }

      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setUploadedFile(file);
        onUpload(file);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    onDragEnter: () => setIsDragActive(true),
    onDragLeave: () => setIsDragActive(false),
    accept: { "application/zip": [".zip"] },
    maxFiles: 1,
    maxSize: 500 * 1024 * 1024,
    disabled: isUploading,
  });

  return (
    <div className="w-full max-w-2xl mx-auto" role="region" aria-label="Zona de upload de arquivo">
      <motion.div
        {...(getRootProps() as React.ComponentProps<typeof motion.div>)}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        whileHover={{ scale: isUploading ? 1 : 1.01 }}
        role="button"
        tabIndex={0}
        aria-label={isUploading ? "Enviando arquivo..." : "Clique ou arraste um arquivo ZIP para fazer upload"}
        aria-busy={isUploading}
        className={cn(
          "upload-zone relative cursor-pointer rounded-2xl p-12 transition-all duration-300",
          "border-2 border-dashed",
          isDragActive
            ? "border-accent-400 bg-accent-400/5 upload-zone-active"
            : "border-brand-500/40 bg-dark-700/50",
          isUploading && "cursor-not-allowed opacity-70",
          !isUploading && "hover:border-brand-400 hover:bg-dark-600/50"
        )}
      >
        <input {...getInputProps()} aria-label="Selecionar arquivo ZIP para upload" />

        {/* Conic spin border effect */}
        <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
          <div
            className={cn(
              "absolute inset-0 opacity-0 transition-opacity duration-300",
              isDragActive && "opacity-100"
            )}
            style={{
              background: "conic-gradient(from 0deg, transparent, rgba(0,212,170,0.2), transparent)",
              animation: "spin 4s linear infinite",
            }}
          />
        </div>

        <AnimatePresence mode="wait">
          {isUploading ? (
            <motion.div
              key="uploading"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="relative">
                <div className="w-20 h-20 rounded-full border-2 border-brand-500/30 flex items-center justify-center">
                  <Zap className="w-8 h-8 text-brand-400 animate-pulse" />
                </div>
                <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-brand-500 animate-spin" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-brand-300">Enviando arquivo...</p>
                <p className="text-sm text-gray-400 mt-1">
                  {uploadedFile && `${uploadedFile.name}`}
                </p>
              </div>
            </motion.div>
          ) : uploadedFile && !error ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="w-20 h-20 rounded-full bg-accent-400/10 border border-accent-400/30 flex items-center justify-center">
                <CheckCircle2 className="w-10 h-10 text-accent-400" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-accent-300">Arquivo selecionado!</p>
                <p className="text-sm text-gray-400 mt-1">{uploadedFile.name}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex flex-col items-center gap-6"
            >
              {/* Icon */}
              <motion.div
                animate={isDragActive ? { scale: 1.1, y: -5 } : { scale: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 300 }}
                className="relative"
              >
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-brand-600/20 to-accent-400/20 border border-brand-500/20 flex items-center justify-center">
                  <FileArchive className="w-12 h-12 text-brand-400" />
                </div>
                <motion.div
                  animate={{ y: isDragActive ? -8 : 0, opacity: isDragActive ? 1 : 0.5 }}
                  className="absolute -top-3 -right-3"
                >
                  <Upload className="w-6 h-6 text-accent-400" />
                </motion.div>
              </motion.div>

              {/* Text */}
              <div className="text-center space-y-2">
                <p className="text-2xl font-bold">
                  {isDragActive ? (
                    <span className="text-gradient-accent">Solte o arquivo aqui!</span>
                  ) : (
                    <span className="text-gradient">Arraste seu arquivo .zip</span>
                  )}
                </p>
                <p className="text-gray-400">
                  ou{" "}
                  <span className="text-brand-400 underline underline-offset-2 cursor-pointer hover:text-brand-300">
                    clique para selecionar
                  </span>
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  Exportação do WhatsApp (.zip) • Máximo 500MB
                </p>
              </div>

              {/* Instructions */}
              <div className="grid grid-cols-3 gap-3 w-full mt-2">
                {[
                  { icon: "📱", label: "Android", desc: "Chat > ⋮ > Exportar" },
                  { icon: "🍎", label: "iPhone", desc: "Chat > ⋯ > Exportar" },
                  { icon: "📦", label: "Inclui mídias", desc: "Com anexos" },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="glass rounded-xl p-3 text-center"
                  >
                    <span className="text-xl">{item.icon}</span>
                    <p className="text-xs font-medium text-gray-200 mt-1">{item.label}</p>
                    <p className="text-xs text-gray-500">{item.desc}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              role="alert"
              aria-live="assertive"
              className="flex items-center gap-2 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30"
            >
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" aria-hidden="true" />
              <p className="text-sm text-red-300">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
