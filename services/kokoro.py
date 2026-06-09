import logging
import time
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
import openai

from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
)
from livekit.agents.utils import is_given

logger = logging.getLogger(__name__)

TTS_SAMPLE_RATE = 24000
TTS_CHANNELS = 1

TTSModels = Literal["tts-1"]
TTSVoices = Literal["af_heart", "af_bella"]


@dataclass
class KokoroTTSOptions:
    """Configuration options for KokoroTTS."""

    model: TTSModels | str
    voice: TTSVoices | str
    speed: float


class KokoroTTS(tts.TTS):
    """TTS implementation using a Kokoro (OpenAI-compatible) server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8880/v1",
        api_key: str = "not-needed",
        model: TTSModels | str = "tts-1",
        voice: TTSVoices | str = "af_heart",
        speed: float = 1.0,
        client: Optional[openai.AsyncClient] = None,
    ) -> None:
        logger.info(f"Using Kokoro TTS API URL: {base_url}")

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=TTS_SAMPLE_RATE,
            num_channels=TTS_CHANNELS,
        )

        self._opts = KokoroTTSOptions(model=model, voice=voice, speed=speed)

        self._client = client or openai.AsyncClient(
            max_retries=0,
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=5.0, write=5.0, pool=5.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=50,
                    keepalive_expiry=120,
                ),
            ),
        )

    def update_options(
        self,
        *,
        model: NotGivenOr[TTSModels | str] = NOT_GIVEN,
        voice: NotGivenOr[TTSVoices | str] = NOT_GIVEN,
        speed: NotGivenOr[float] = NOT_GIVEN,
    ) -> None:
        if is_given(model):
            self._opts.model = model
        if is_given(voice):
            self._opts.voice = voice
        if is_given(speed):
            self._opts.speed = speed

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "KokoroTTSStream":
        return KokoroTTSStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            opts=self._opts,
            client=self._client,
        )


class KokoroTTSStream(tts.ChunkedStream):
    """Stream implementation for KokoroTTS (current AudioEmitter API)."""

    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options: APIConnectOptions,
        opts: KokoroTTSOptions,
        client: openai.AsyncClient,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._client = client
        self._opts = opts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        try:
            start_time = time.time()
            async with self._client.audio.speech.with_streaming_response.create(
                input=self._input_text,
                model=self._opts.model,
                voice=self._opts.voice,
                response_format="pcm",  # raw PCM 16-bit mono @ 24kHz
                speed=self._opts.speed,
                timeout=httpx.Timeout(30, connect=self._conn_options.timeout),
            ) as stream:
                # Tell the framework what's coming; it handles framing.
                output_emitter.initialize(
                    request_id=request_id,
                    sample_rate=TTS_SAMPLE_RATE,
                    num_channels=TTS_CHANNELS,
                    mime_type="audio/pcm",
                )
                async for data in stream.iter_bytes():
                    output_emitter.push(data)

            output_emitter.flush()
            logger.info(
                f"Kokoro TTS synthesis completed in {(time.time() - start_time) * 1000:.1f}ms"
            )

        except openai.APITimeoutError:
            raise APITimeoutError()
        except openai.APIStatusError as e:
            raise APIStatusError(
                e.message,
                status_code=e.status_code,
                request_id=e.request_id,
                body=e.body,
            )
        except Exception as e:
            raise APIConnectionError() from e