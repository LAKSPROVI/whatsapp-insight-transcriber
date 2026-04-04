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
  const [consentChecked, setConsentChecked] = useState(false);
  const [showPrivacyPolicy, setShowPrivacyPolicy] = useState(false);

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
        if (!consentChecked) {
          setError("Voce deve aceitar a Politica de Privacidade e consentir com o processamento antes de fazer upload.");
          return;
        }
        setUploadedFile(file);
        onUpload(file);
      }
    },
    [onUpload, consentChecked]
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

      {/* LGPD Consent Checkbox */}
      <div className="mt-4 space-y-3">
        <label className="flex items-start gap-3 cursor-pointer group">
          <input
            type="checkbox"
            checked={consentChecked}
            onChange={(e) => {
              setConsentChecked(e.target.checked);
              if (e.target.checked) setError(null);
            }}
            className="mt-1 w-4 h-4 rounded border-brand-500/40 bg-dark-700 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
            aria-label="Aceitar Politica de Privacidade e consentir com o processamento"
          />
          <span className="text-sm text-gray-400 group-hover:text-gray-300 transition-colors">
            Declaro que li e aceito a{" "}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                setShowPrivacyPolicy(true);
              }}
              className="text-brand-400 underline underline-offset-2 hover:text-brand-300"
            >
              Politica de Privacidade
            </button>
            {" "}e consinto com o processamento dos dados enviados por inteligencia artificial,
            incluindo a transferencia internacional para a API Anthropic (EUA) com redacao previa de
            dados pessoais identificaveis (PII), conforme a LGPD (Lei 13.709/2018).
          </span>
        </label>

        <p className="text-xs text-gray-500 pl-7">
          Seus dados serao retidos por no maximo 90 dias e voce pode solicitar exclusao a qualquer momento.
        </p>
      </div>

      {/* Privacy Policy Modal */}
      <AnimatePresence>
        {showPrivacyPolicy && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setShowPrivacyPolicy(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
              className="bg-dark-800 border border-brand-500/20 rounded-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            >
              <h2 className="text-xl font-bold text-white mb-4">Politica de Privacidade</h2>
              <div className="text-sm text-gray-300 space-y-3">
                <p><strong>1. CONTROLADOR DOS DADOS</strong></p>
                <p>O controlador responsavel pelo tratamento dos seus dados pessoais e o operador da plataforma WhatsApp Insight Transcriber.</p>
                <p><strong>2. DADOS COLETADOS</strong></p>
                <p>Dados de cadastro, conversas do WhatsApp (textos, audios, imagens, videos), dados de uso e dados gerados pela IA.</p>
                <p><strong>3. BASE LEGAL</strong></p>
                <p>Consentimento explicito do usuario (Art. 7, I, LGPD).</p>
                <p><strong>4. TRANSFERENCIA INTERNACIONAL</strong></p>
                <p>Textos sao enviados a API Anthropic (EUA). PII e redactado antes do envio.</p>
                <p><strong>5. RETENCAO</strong></p>
                <p>Conversas retidas por no maximo 90 dias.</p>
                <p><strong>6. SEUS DIREITOS (Art. 18 LGPD)</strong></p>
                <p>Acessar, corrigir, excluir dados. Revogar consentimento. Portabilidade.</p>
                <p><strong>7. SEGURANCA</strong></p>
                <p>TLS/HTTPS, JWT, RBAC, cadeia de custodia, redacao PII, backups.</p>
                <p><strong>8. CONTATO DPO</strong></p>
                <p>dpo@whatsapp-insight.com</p>
              </div>
              <button
                onClick={() => setShowPrivacyPolicy(false)}
                className="mt-6 w-full py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition-colors"
              >
                Fechar
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
