import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  getHealth,
  createVoiceSession,
  sendVoiceConsent,
  sendVoiceTurn,
  sendVoiceAnswer,
} from '../api';
import type { VoiceSessionOut, Health } from '../types';
import { resampleTo16kMono, encodeWAV } from '../utils/audio';

type MicState = 'idle' | 'recording' | 'processing' | 'speaking';

export default function VoiceBookingPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [session, setSession] = useState<VoiceSessionOut | null>(null);
  const [consented, setConsented] = useState<boolean>(false);
  const [micState, setMicState] = useState<MicState>('idle');
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const timerIntervalRef = useRef<any>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  // 1. Initial Health Check & Session Creation
  useEffect(() => {
    let mounted = true;
    getHealth()
      .then((h) => {
        if (!mounted) return;
        setHealth(h);
        if (h.voice !== 'down') {
          return createVoiceSession().then((sess) => {
            if (mounted) setSession(sess);
          });
        }
      })
      .catch((_err) => {
        if (!mounted) return;
        setErrorMsg('Cannot connect to Vaari server.');
      });

    return () => {
      mounted = false;
      stopAudioAnalysis();
    };
  }, []);

  // 2. Play prompt audio whenever session prompt changes
  useEffect(() => {
    if (!session?.prompt?.audio_url || !consented) return;

    if (audioElementRef.current) {
      audioElementRef.current.pause();
    }

    const audio = new Audio(session.prompt.audio_url);
    audioElementRef.current = audio;
    setMicState('speaking');

    audio.onended = () => {
      setMicState('idle');
    };
    audio.onerror = () => {
      // Audio playback failed (e.g. mock or missing wav), return to idle
      setMicState('idle');
    };

    audio.play().catch(() => {
      // Browser autoplay policy might block before user interaction
      setMicState('idle');
    });

    return () => {
      audio.pause();
    };
  }, [session?.prompt?.key, session?.prompt?.audio_url, consented]);

  const handleConsent = async () => {
    if (!session) return;
    try {
      setMicState('processing');
      const updated = await sendVoiceConsent(session.session_id);
      setSession(updated);
      setConsented(true);
      setMicState('idle');
    } catch (err: any) {
      setErrorMsg(err.message || 'Consent submission failed.');
      setMicState('idle');
    }
  };

  const startAudioAnalysis = (stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateMeter = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
        animFrameRef.current = requestAnimationFrame(updateMeter);
      };
      updateMeter();
    } catch {
      // AudioContext analysis optional
    }
  };

  const stopAudioAnalysis = () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setAudioLevel(0);
  };

  const startRecording = async () => {
    if (!consented || !session) return;
    if (micState === 'recording') {
      stopRecording();
      return;
    }
    setErrorMsg(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      startAudioAnalysis(stream);

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stopAudioAnalysis();
        stream.getTracks().forEach((track) => track.stop());
        clearInterval(timerIntervalRef.current);
        setRecordingSeconds(0);

        setMicState('processing');
        const rawBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType });

        let wavBlob: Blob;
        try {
          // Convert browser audio blob into 16 kHz mono 16-bit PCM WAV using AudioContext
          const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
          const decodeCtx = new AudioCtx();
          const arrayBuffer = await rawBlob.arrayBuffer();
          const decodedBuffer = await decodeCtx.decodeAudioData(arrayBuffer);
          wavBlob = await resampleTo16kMono(decodedBuffer);
          decodeCtx.close();
        } catch {
          // Fallback if headless browser / hardware lacks audio decoding capability
          wavBlob = encodeWAV(new Float32Array(16000), 16000);
        }

        try {
          // Send to backend voice turn API
          const updated = await sendVoiceTurn(session.session_id, wavBlob);
          setSession(updated);
        } catch (err: any) {
          setErrorMsg(err.message || 'Failed to process voice turn.');
        } finally {
          setMicState('idle');
        }
      };

      mediaRecorder.start(250); // Slice every 250ms
      setMicState('recording');
      setRecordingSeconds(0);

      // 15-second hardware cap
      let sec = 0;
      timerIntervalRef.current = setInterval(() => {
        sec += 1;
        setRecordingSeconds(sec);
        if (sec >= 15) {
          stopRecording();
        }
      }, 1000);
    } catch (err: any) {
      setErrorMsg('Microphone access denied or unavailable: ' + (err.message || err));
      setMicState('idle');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  };

  const handleConfirmAnswer = async (answer: 'yes' | 'no') => {
    if (!session) return;
    try {
      setMicState('processing');
      const updated = await sendVoiceAnswer(session.session_id, answer);
      setSession(updated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Confirmation submission failed.');
    } finally {
      setMicState('idle');
    }
  };

  const isVoiceDown = health?.voice === 'down';

  return (
    <div className="voice-booking-page" id="voice-page">
      {/* Top Fallback Bar */}
      <div className="voice-top-bar">
        <Link to="/intake" className="voice-type-link" id="voice-top-intake-link">
          ⌨️ ਫ਼ਾਰਮ ਭਰ ਕੇ ਬੁੱਕ ਕਰੋ / Type your booking instead &rarr;
        </Link>
      </div>

      {/* Voice Down Warning */}
      {isVoiceDown && (
        <div className="voice-down-alert" id="voice-down-banner" role="alert">
          <h3>⚠️ ਆਵਾਜ਼ ਸੇਵਾ ਉਪਲਬਧ ਨਹੀਂ ਹੈ / Voice Service Down</h3>
          <p>
            ਸਾਡੀ ਆਵਾਜ਼ ਪ੍ਰਣਾਲੀ ਫਿਲਹਾਲ ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਸਾਧਾਰਨ ਫ਼ਾਰਮ ਦੀ ਵਰਤੋਂ ਕਰੋ।
          </p>
          <p className="en-sub">
            The voice service is currently unavailable on this machine. Please use the form.
          </p>
          <Link to="/intake" className="btn-primary" style={{ display: 'inline-block', marginTop: 12 }}>
            ਫ਼ਾਰਮ 'ਤੇ ਜਾਓ / Go to Form
          </Link>
        </div>
      )}

      {/* Consent & Privacy Notice */}
      {!consented && !isVoiceDown && (
        <div className="voice-card voice-consent-card" id="voice-consent-box">
          <div className="assistant-tag">
            🤖 ਆਟੋਮੇਟਿਡ ਸਿਸਟਮ / Automated Assistant
          </div>
          <h2>ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ!</h2>
          <p className="consent-punjabi">
            ਮੈਂ ਵਾਰੀ ਦਾ ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ ਹਾਂ (ਮੈਂ ਇੱਕ ਕੰਪਿਊਟਰ ਹਾਂ, ਕੋਈ ਵਿਅਕਤੀ ਨਹੀਂ)।
            ਤੁਹਾਡੀ ਆਵਾਜ਼ ਇਸ ਕੰਪਿਊਟਰ 'ਤੇ ਲਿਖਤ ਵਿੱਚ ਬਦਲੀ ਜਾਵੇਗੀ ਅਤੇ ਤੁਰੰਤ ਮਿਟਾ ਦਿੱਤੀ ਜਾਵੇਗੀ। ਅਸੀਂ ਸਿਰਫ਼ ਤੁਹਾਡੇ ਬੁਕਿੰਗ ਵੇਰਵੇ ਰੱਖਾਂਗੇ।
          </p>
          <p className="consent-english">
            I am Vaari's automated booking assistant. Your voice is converted to text locally on this computer and deleted immediately; only booking details are kept.
          </p>
          <button
            id="voice-consent-btn"
            className="btn-primary voice-consent-btn"
            onClick={handleConsent}
            disabled={micState === 'processing'}
          >
            ✓ ਮੈਂ ਸਹਿਮਤ ਹਾਂ / I Agree & Continue
          </button>
        </div>
      )}

      {/* Main Voice Interactive Flow */}
      {consented && !isVoiceDown && (
        <div className="voice-flow">
          {/* Progress Indicator */}
          <div className="voice-progress-line" id="voice-progress-tracker">
            <span className={`prog-item ${session?.collected_fields?.phone ? 'done' : session?.current_field === 'phone' ? 'active' : ''}`}>
              ਫ਼ੋਨ / Phone {session?.collected_fields?.phone && '✓'}
            </span>
            <span className="prog-sep">&rsaquo;</span>
            <span className={`prog-item ${session?.collected_fields?.village ? 'done' : session?.current_field === 'village' ? 'active' : ''}`}>
              ਪਿੰਡ / Village {session?.collected_fields?.village && '✓'}
            </span>
            <span className="prog-sep">&rsaquo;</span>
            <span className={`prog-item ${session?.collected_fields?.acres ? 'done' : session?.current_field === 'acres' ? 'active' : ''}`}>
              ਏਕੜ / Acres {session?.collected_fields?.acres && '✓'}
            </span>
            <span className="prog-sep">&rsaquo;</span>
            <span className={`prog-item ${session?.collected_fields?.machine ? 'done' : session?.current_field === 'machine' ? 'active' : ''}`}>
              ਮਸ਼ੀਨ / Machine {session?.collected_fields?.machine && '✓'}
            </span>
            <span className="prog-sep">&rsaquo;</span>
            <span className={`prog-item ${session?.collected_fields?.harvest_date ? 'done' : session?.current_field === 'harvest_date' ? 'active' : ''}`}>
              ਤਾਰੀਖ਼ / Date {session?.collected_fields?.harvest_date && '✓'}
            </span>
          </div>

          {/* Current Spoken Prompt Display */}
          {session?.prompt && (
            <div className="voice-card voice-prompt-card" id="voice-current-prompt">
              <div className="prompt-pa">{session.prompt.text_pa}</div>
              <div className="prompt-en">{session.prompt.text_en}</div>
              {session.transcript && (
                <div className="prompt-transcript">
                  <small>ਤੁਸੀਂ ਕਿਹਾ / You said: "{session.transcript}"</small>
                </div>
              )}
            </div>
          )}

          {/* Read-back Summary & Big Yes/No Buttons */}
          {session?.state === 'confirming' && (
            <div className="voice-card voice-summary-card" id="voice-confirm-card">
              <h3>ਬੁਕਿੰਗ ਵੇਰਵਿਆਂ ਦੀ ਜਾਂਚ ਕਰੋ / Verify Booking Details</h3>
              <div className="summary-grid">
                <div className="grid-label">ਫ਼ੋਨ / Phone:</div>
                <div className="grid-val" id="summary-phone">{session.collected_fields.phone || '—'}</div>

                <div className="grid-label">ਪਿੰਡ / Village:</div>
                <div className="grid-val" id="summary-village">{session.collected_fields.village || '—'}</div>

                <div className="grid-label">ਏਕੜ / Acres:</div>
                <div className="grid-val" id="summary-acres">{session.collected_fields.acres ? `${session.collected_fields.acres} ਏਕੜ` : '—'}</div>

                <div className="grid-label">ਮਸ਼ੀਨ / Machine:</div>
                <div className="grid-val" id="summary-machine">{session.collected_fields.machine || '—'}</div>

                <div className="grid-label">ਤਾਰੀਖ਼ / Date:</div>
                <div className="grid-val" id="summary-date">{session.collected_fields.harvest_date || '—'}</div>
              </div>

              <div className="confirm-buttons-row">
                <button
                  id="voice-confirm-yes"
                  className="btn-confirm-yes"
                  onClick={() => handleConfirmAnswer('yes')}
                  disabled={micState === 'processing'}
                >
                  <span className="btn-icon">✓</span>
                  <span className="btn-text">ਹਾਂ, ਸਹੀ ਹੈ<br /><small>Yes, Confirm</small></span>
                </button>
                <button
                  id="voice-confirm-no"
                  className="btn-confirm-no"
                  onClick={() => handleConfirmAnswer('no')}
                  disabled={micState === 'processing'}
                >
                  <span className="btn-icon">✗</span>
                  <span className="btn-text">ਨਹੀਂ, ਰੱਦ ਕਰੋ<br /><small>No, Cancel</small></span>
                </button>
              </div>
            </div>
          )}

          {/* Final Confirmed State */}
          {session?.state === 'confirmed' && (
            <div className="voice-card voice-success-card" id="voice-success-box">
              <div className="success-badge">✓</div>
              <h2>ਬੁਕਿੰਗ ਪੱਕੀ ਹੋ ਗਈ ਹੈ! / Booking Confirmed!</h2>
              {session.slot_date && (
                <p className="slot-date-info">
                  ਮਸ਼ੀਨ ਆਉਣ ਦੀ ਤਾਰੀਖ਼: <strong>{session.slot_date}</strong>
                </p>
              )}
              {session.request_id && (
                <p className="request-id-info">
                  ਬੇਨਤੀ ਨੰਬਰ / Request ID: <code>{session.request_id}</code>
                </p>
              )}
              <Link to="/desk" className="btn-primary" style={{ display: 'inline-block', marginTop: 16 }}>
                ਡੈਸਕ 'ਤੇ ਦੇਖੋ / View on Desk
              </Link>
            </div>
          )}

          {/* Giant Microphone Button */}
          {session?.state !== 'confirmed' && session?.state !== 'cancelled' && (
            <div className="voice-mic-container">
              <button
                id="voice-mic-btn"
                className={`giant-mic-btn ${micState}`}
                onClick={startRecording}
                disabled={micState === 'processing'}
                aria-label={micState === 'recording' ? 'Stop recording' : 'Start speaking'}
              >
                {micState === 'recording' && <span className="mic-pulse-ring" />}
                {micState === 'speaking' && <span className="speaking-pulse-ring" />}
                <span className="mic-icon">
                  {micState === 'processing' ? '⏳' : micState === 'recording' ? '⏹' : micState === 'speaking' ? '🔊' : '🎙️'}
                </span>
              </button>

              <div className="mic-status-label">
                {micState === 'recording' && (
                  <span className="status-recording">
                    ਸੁਣ ਰਿਹਾ ਹਾਂ... ({recordingSeconds}s / 15s) ਰੋਕਣ ਲਈ ਦਬਾਓ
                  </span>
                )}
                {micState === 'processing' && <span className="status-processing">ਪ੍ਰਕਿਰਿਆ ਜਾਰੀ ਹੈ... Processing...</span>}
                {micState === 'speaking' && <span className="status-speaking">ਸਹਾਇਕ ਬੋਲ ਰਿਹਾ ਹੈ... Listening to reply</span>}
                {micState === 'idle' && (
                  <span className="status-idle">
                    ਬੋਲਣ ਲਈ ਮਾਈਕ ਦਬਾਓ / Tap mic to speak
                  </span>
                )}
              </div>

              {/* Audio Volume Level Meter */}
              {micState === 'recording' && (
                <div className="audio-level-meter" aria-hidden="true">
                  <div
                    className="audio-level-bar"
                    style={{ width: `${Math.max(5, audioLevel)}%` }}
                  />
                </div>
              )}
            </div>
          )}

          {errorMsg && (
            <div className="voice-error-banner" role="alert">
              {errorMsg}
            </div>
          )}
        </div>
      )}

      {/* Bottom Fallback Bar */}
      <div className="voice-bottom-bar">
        <Link to="/intake" className="voice-type-link" id="voice-bottom-intake-link">
          ਕੀਬੋਰਡ ਨਾਲ ਲਿਖੋ / Type your booking instead &rarr;
        </Link>
      </div>
    </div>
  );
}
