"""Assembly boundary for independent DeBot and on-chain mint sources."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass

from .bsc_mint_rpc import BscMintRpcClient
from .catalyst_mint_state import CatalystMintState
from .chain_mint_monitor import BscMintMonitor
from .chain_mint_state import ChainMintCheckpointStore
from .mint_location_store import MintLocationStore
from .mint_monitor import NarrativeMintMonitor
from .settings import NarrativeSettings


@dataclass(frozen=True, slots=True)
class NarrativeMintSources:
    debot: NarrativeMintMonitor
    catalyst: CatalystMintState
    locations: MintLocationStore
    rpc: BscMintRpcClient
    chain: BscMintMonitor


def build_mint_sources(
    settings: NarrativeSettings, resources: ExitStack,
) -> NarrativeMintSources:
    debot = NarrativeMintMonitor.from_credentials(
        credential_file=settings.debot_cookie_file,
        timeout_seconds=settings.debot_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
        poll_seconds=settings.mint_poll_seconds,
    )
    resources.callback(debot.close)
    locations = MintLocationStore(settings.mint_location_database)
    resources.callback(locations.close)
    rpc = BscMintRpcClient(
        settings.bsc_rpc_endpoints,
        timeout_seconds=settings.chain_mint_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
    )
    resources.callback(rpc.close)
    chain = BscMintMonitor(
        rpc,
        ChainMintCheckpointStore(settings.chain_mint_checkpoint_path),
        poll_seconds=settings.chain_mint_poll_seconds,
        startup_lookback_blocks=settings.chain_mint_startup_lookback_blocks,
        max_catchup_blocks=settings.chain_mint_max_catchup_blocks,
    )
    return NarrativeMintSources(
        debot=debot,
        catalyst=CatalystMintState(settings.catalyst_mint_state_path),
        locations=locations,
        rpc=rpc,
        chain=chain,
    )
