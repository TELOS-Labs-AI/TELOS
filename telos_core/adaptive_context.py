"""
TELOS Adaptive Context System

Multi-tier, phase-aware, pattern-classified context management for
reducing false-positive drift detection in conversational AI.

Based on ADAPTIVE_CONTEXT_PROPOSAL.md (December 18, 2025)

Key features:
- Message type classification (DIRECT, FOLLOW_UP, CLARIFICATION, ANAPHORA)
- Conversation phase detection (EXPLORATION, FOCUS, DRIFT, RECOVERY)
- Multi-tier context buffer with weighted embeddings
- Adaptive threshold calculation with governance safeguards
"""

import re
import logging
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS - Imported from Single Source of Truth
# =============================================================================
from telos_core.constants import (
    FIDELITY_GREEN,
    INTERVENTION_THRESHOLD,
)

# Governance Safeguards (MUST NOT BE VIOLATED)
HARD_FLOOR = 0.20  # Never boost fidelity below this threshold
MAX_BOOST = 0.20   # Threshold can never be reduced by more than this

# =============================================================================
# SEMANTIC CONTINUITY INHERITANCE (SCI) - v4.0 (2025-12-30)
# =============================================================================

# Continuity thresholds (cosine similarity to previous turn)
SCI_STRONG_CONTINUITY = 0.70    # Clear semantic continuation
SCI_MODERATE_CONTINUITY = 0.50  # Moderate connection
SCI_WEAK_CONTINUITY = 0.30      # Minimal connection

# Decay factors (how much of previous fidelity is inherited)
SCI_STRONG_DECAY = 0.99    # Nearly full inheritance
SCI_MODERATE_DECAY = 0.95  # Standard decay
SCI_WEAK_DECAY = 0.90      # Noticeable decay

# SCI feature flag
SCI_ENABLED = True


# =============================================================================
# SCI HELPER FUNCTIONS
# =============================================================================

def calculate_semantic_continuity(
    current_embedding: np.ndarray,
    previous_turn_embeddings: List[np.ndarray]
) -> Tuple[float, int]:
    """
    Calculate semantic continuity between current message and previous turn.

    Args:
        current_embedding: Embedding of current user input (normalized)
        previous_turn_embeddings: List of embeddings from previous turn

    Returns:
        Tuple of (max_continuity_score, best_embedding_index)
    """
    if not previous_turn_embeddings or len(previous_turn_embeddings) == 0:
        return 0.0, -1

    current_norm = current_embedding / np.linalg.norm(current_embedding)

    similarities = []
    for emb in previous_turn_embeddings:
        emb_norm = emb / np.linalg.norm(emb)
        sim = float(np.dot(current_norm, emb_norm))
        similarities.append(sim)

    max_sim = max(similarities)
    best_idx = similarities.index(max_sim)

    return max_sim, best_idx


def get_decay_factor(continuity_score: float) -> float:
    """
    Get the appropriate decay factor based on continuity strength.

    Args:
        continuity_score: Cosine similarity to previous turn (0.0-1.0)

    Returns:
        Decay factor (0.90-0.99)
    """
    if continuity_score >= SCI_STRONG_CONTINUITY:
        return SCI_STRONG_DECAY
    elif continuity_score >= SCI_MODERATE_CONTINUITY:
        return SCI_MODERATE_DECAY
    else:
        return SCI_WEAK_DECAY


def apply_continuity_inheritance(
    direct_fidelity: float,
    continuity_score: float,
    previous_fidelity: float
) -> Tuple[float, str]:
    """
    Apply Semantic Continuity Inheritance to compute adjusted fidelity.

    Args:
        direct_fidelity: Raw fidelity computed directly against PA
        continuity_score: Semantic similarity to previous turn (0.0-1.0)
        previous_fidelity: Fidelity score from the previous turn

    Returns:
        Tuple of (adjusted_fidelity, method_used)
    """
    if continuity_score < SCI_WEAK_CONTINUITY:
        return direct_fidelity, "direct_only"

    decay = get_decay_factor(continuity_score)
    inherited_fidelity = previous_fidelity * decay

    if direct_fidelity >= inherited_fidelity:
        return direct_fidelity, "direct_preferred"
    else:
        return inherited_fidelity, "inherited"


# Base intervention threshold
BASE_THRESHOLD = INTERVENTION_THRESHOLD  # 0.48

# Tier configuration
TIER1_THRESHOLD = FIDELITY_GREEN  # 0.70
TIER2_THRESHOLD = 0.35
TIER3_THRESHOLD = 0.25

TIER1_CAPACITY = 5
TIER2_CAPACITY = 3
TIER3_CAPACITY = 2

TIER1_WEIGHT = 0.6
TIER2_WEIGHT = 0.3
TIER3_WEIGHT = 0.1

# Recency decay factor
RECENCY_DECAY = 0.8

# Phase detection window
PHASE_WINDOW_SIZE = 5


# =============================================================================
# MESSAGE TYPE CLASSIFICATION
# =============================================================================

class MessageType(Enum):
    """Classification of user message types with associated threshold adjustments."""
    DIRECT = "direct"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    ANAPHORA = "anaphora"


MESSAGE_TYPE_THRESHOLDS = {
    MessageType.DIRECT: 0.70,
    MessageType.FOLLOW_UP: 0.35,
    MessageType.CLARIFICATION: 0.25,
    MessageType.ANAPHORA: 0.25,
}

MESSAGE_PATTERNS = {
    MessageType.CLARIFICATION: [
        r'^(what|how|why|can you|could you)\s+(did you mean|do you mean|does that mean)',
        r'^(i don\'?t understand|explain|clarify|what was)',
        r'^(say that again|repeat|what\?)',
        r'(what do you mean|elaborate on that|tell me more about what you said)',
    ],
    MessageType.ANAPHORA: [
        r'^(it|this|that|these|those|they|them)\s+(is|are|was|were|has|have|should|could|would|will)',
        r'^(tell me more about (it|this|that))',
        r'^(expand on (it|this|that))',
        r'^(and|also|plus|furthermore|additionally)\s+',
        r'^(what about|how about)\s+(it|this|that|them)',
        r'\b(for|about|on|to|with|of)\s+(that|this|it|them|those)\s*[?.!]?\s*$',
        r'\b(that|this|it)\s*[?.!]?\s*$',
        r'\b(do|understand|know|prepare|ready|handle)\s+.{0,20}\b(that|this|it)\s*[?.!]?\s*$',
    ],
    MessageType.FOLLOW_UP: [
        r'^(ok|okay|alright|sure|yes|yeah|got it|i see|thanks)',
        r'^(now|next|then|after that|moving on)',
        r'^(can you also|also|additionally|furthermore)',
        r'^(and|but|so|however)',
        r'^(what else|anything else|is there more)',
        r'^(tell me more|go on|continue|keep going|more|please continue)',
        r'^(explain more|elaborate|more details|more info)',
    ],
}


def classify_message_type(
    message: str,
    recent_context: Optional[List[str]] = None,
    topic_continuity_score: Optional[float] = None
) -> MessageType:
    """
    Classify a user message by its conversational function.

    Args:
        message: The user's input text
        recent_context: Previous messages for context (optional)
        topic_continuity_score: Semantic similarity to recent messages (optional)

    Returns:
        MessageType classification
    """
    message_lower = message.lower().strip()

    for pattern in MESSAGE_PATTERNS[MessageType.CLARIFICATION]:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return MessageType.CLARIFICATION

    for pattern in MESSAGE_PATTERNS[MessageType.ANAPHORA]:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return MessageType.ANAPHORA

    for pattern in MESSAGE_PATTERNS[MessageType.FOLLOW_UP]:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return MessageType.FOLLOW_UP

    if topic_continuity_score is not None and topic_continuity_score > 0.7:
        return MessageType.FOLLOW_UP

    return MessageType.DIRECT


# =============================================================================
# CONVERSATION PHASE DETECTION
# =============================================================================

class ConversationPhase(Enum):
    """Phases of a conversation affecting threshold behavior."""
    EXPLORATION = "exploration"
    FOCUS = "focus"
    DRIFT = "drift"
    RECOVERY = "recovery"


PHASE_MODIFIERS = {
    ConversationPhase.EXPLORATION: -0.10,
    ConversationPhase.FOCUS: 0.0,
    ConversationPhase.DRIFT: 0.10,
    ConversationPhase.RECOVERY: -0.05,
}


@dataclass
class PhaseDetector:
    """Detects conversation phase based on fidelity trajectory."""
    window_size: int = PHASE_WINDOW_SIZE
    fidelity_history: deque = field(default_factory=lambda: deque(maxlen=PHASE_WINDOW_SIZE))
    current_phase: ConversationPhase = ConversationPhase.EXPLORATION
    turns_in_phase: int = 0

    def update(self, fidelity: float) -> ConversationPhase:
        self.fidelity_history.append(fidelity)
        self.turns_in_phase += 1

        if len(self.fidelity_history) < 3:
            return self.current_phase

        recent = list(self.fidelity_history)
        avg_recent = np.mean(recent[-3:])
        avg_older = np.mean(recent[:-3]) if len(recent) > 3 else avg_recent
        trend = avg_recent - avg_older

        new_phase = self._detect_phase(avg_recent, trend)

        if new_phase != self.current_phase:
            self.current_phase = new_phase
            self.turns_in_phase = 0

        return self.current_phase

    def _detect_phase(self, avg_fidelity: float, trend: float) -> ConversationPhase:
        if len(self.fidelity_history) <= 3:
            return ConversationPhase.EXPLORATION
        if avg_fidelity >= 0.65 and abs(trend) < 0.05:
            return ConversationPhase.FOCUS
        if trend < -0.05 and avg_fidelity < 0.60:
            return ConversationPhase.DRIFT
        if trend > 0.05 and self.current_phase == ConversationPhase.DRIFT:
            return ConversationPhase.RECOVERY
        if abs(trend) < 0.05:
            return ConversationPhase.FOCUS
        return self.current_phase

    def reset(self):
        self.fidelity_history.clear()
        self.current_phase = ConversationPhase.EXPLORATION
        self.turns_in_phase = 0


# =============================================================================
# MULTI-TIER CONTEXT BUFFER
# =============================================================================

@dataclass
class TieredMessage:
    """A message with its embedding and fidelity stored in a tier."""
    text: str
    embedding: np.ndarray
    fidelity_score: float
    timestamp: datetime
    message_type: MessageType
    tier: int

    def __post_init__(self):
        if isinstance(self.embedding, list):
            self.embedding = np.array(self.embedding)


class MultiTierContextBuffer:
    """
    Three-tier context buffer for managing conversation history.

    Tier 1: High fidelity messages (>= 0.70) - 5 messages, weight 0.6
    Tier 2: Medium fidelity (0.35-0.70) - 3 messages, weight 0.3
    Tier 3: Low fidelity (0.25-0.35) - 2 messages, weight 0.1
    """

    def __init__(self):
        self.tier1: deque = deque(maxlen=TIER1_CAPACITY)
        self.tier2: deque = deque(maxlen=TIER2_CAPACITY)
        self.tier3: deque = deque(maxlen=TIER3_CAPACITY)
        self.ai_response_buffer: deque = deque(maxlen=5)
        self.previous_turn_embeddings: List[np.ndarray] = []
        self.previous_turn_fidelity: Optional[float] = None

    def add_message(
        self,
        text: str,
        embedding: np.ndarray,
        fidelity_score: float,
        message_type: MessageType = MessageType.DIRECT
    ) -> Optional[int]:
        if fidelity_score < TIER3_THRESHOLD:
            return None

        msg = TieredMessage(
            text=text,
            embedding=embedding,
            fidelity_score=fidelity_score,
            timestamp=datetime.now(),
            message_type=message_type,
            tier=self._get_tier_for_fidelity(fidelity_score)
        )

        if fidelity_score >= TIER1_THRESHOLD:
            self.tier1.append(msg)
            return 1
        elif fidelity_score >= TIER2_THRESHOLD:
            self.tier2.append(msg)
            return 2
        else:
            self.tier3.append(msg)
            return 3

    def _get_tier_for_fidelity(self, fidelity: float) -> int:
        if fidelity >= TIER1_THRESHOLD:
            return 1
        elif fidelity >= TIER2_THRESHOLD:
            return 2
        else:
            return 3

    def get_all_messages(self) -> List[TieredMessage]:
        all_msgs = list(self.tier1) + list(self.tier2) + list(self.tier3)
        return sorted(all_msgs, key=lambda m: m.timestamp)

    def get_weighted_context_embedding(self) -> Optional[np.ndarray]:
        all_msgs = self.get_all_messages()
        if not all_msgs:
            return None

        embeddings = []
        weights = []

        for i, msg in enumerate(all_msgs):
            recency_weight = RECENCY_DECAY ** (len(all_msgs) - 1 - i)
            if msg.tier == 1:
                tier_weight = TIER1_WEIGHT
            elif msg.tier == 2:
                tier_weight = TIER2_WEIGHT
            else:
                tier_weight = TIER3_WEIGHT

            embeddings.append(msg.embedding)
            weights.append(recency_weight * tier_weight)

        weights = np.array(weights)
        weights = weights / np.sum(weights)
        embeddings = np.array(embeddings)
        weighted_embedding = np.average(embeddings, axis=0, weights=weights)

        norm = np.linalg.norm(weighted_embedding)
        if norm > 0:
            weighted_embedding = weighted_embedding / norm

        return weighted_embedding

    def get_recent_texts(self, n: int = 3) -> List[str]:
        all_msgs = self.get_all_messages()
        return [m.text for m in all_msgs[-n:]]

    def get_all_embeddings(self) -> List[np.ndarray]:
        return [msg.embedding for msg in self.get_all_messages()]

    def add_ai_response(self, text: str, embedding: np.ndarray) -> None:
        if isinstance(embedding, list):
            embedding = np.array(embedding)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        self.ai_response_buffer.append({
            'text': text[:200],
            'embedding': embedding,
            'timestamp': datetime.now()
        })

    def get_ai_response_embeddings(self) -> List[np.ndarray]:
        return [resp['embedding'] for resp in self.ai_response_buffer]

    def get_all_context_embeddings(self) -> List[np.ndarray]:
        return self.get_all_embeddings() + self.get_ai_response_embeddings()

    def clear(self):
        self.tier1.clear()
        self.tier2.clear()
        self.tier3.clear()
        self.ai_response_buffer.clear()
        self.previous_turn_embeddings = []
        self.previous_turn_fidelity = None

    def __len__(self) -> int:
        return len(self.tier1) + len(self.tier2) + len(self.tier3)

    def set_previous_turn(
        self,
        user_embedding: np.ndarray,
        ai_embedding: Optional[np.ndarray],
        fidelity: float
    ) -> None:
        self.previous_turn_embeddings = []
        if isinstance(user_embedding, list):
            user_embedding = np.array(user_embedding)
        user_norm = np.linalg.norm(user_embedding)
        if user_norm > 0:
            self.previous_turn_embeddings.append(user_embedding / user_norm)

        if ai_embedding is not None:
            if isinstance(ai_embedding, list):
                ai_embedding = np.array(ai_embedding)
            ai_norm = np.linalg.norm(ai_embedding)
            if ai_norm > 0:
                self.previous_turn_embeddings.append(ai_embedding / ai_norm)

        self.previous_turn_fidelity = fidelity

    def get_previous_turn_data(self) -> Tuple[List[np.ndarray], Optional[float]]:
        return self.previous_turn_embeddings, self.previous_turn_fidelity

    def has_previous_turn(self) -> bool:
        return len(self.previous_turn_embeddings) > 0 and self.previous_turn_fidelity is not None


# =============================================================================
# ADAPTIVE THRESHOLD CALCULATOR
# =============================================================================

class AdaptiveThresholdCalculator:
    """Calculates adaptive intervention thresholds."""

    def calculate_threshold(
        self,
        message_type: MessageType,
        phase: ConversationPhase,
        base_threshold: float = BASE_THRESHOLD
    ) -> Tuple[float, Dict[str, Any]]:
        type_threshold = MESSAGE_TYPE_THRESHOLDS.get(message_type, 0.70)
        phase_modifier = PHASE_MODIFIERS.get(phase, 0.0)

        raw_boost = base_threshold - type_threshold
        capped_boost = min(raw_boost, MAX_BOOST)

        if phase == ConversationPhase.DRIFT:
            capped_boost = 0.0

        adjusted = base_threshold - capped_boost + phase_modifier
        final_threshold = max(adjusted, HARD_FLOOR)

        metadata = {
            "message_type": message_type.value,
            "phase": phase.value,
            "base_threshold": base_threshold,
            "type_threshold": type_threshold,
            "phase_modifier": phase_modifier,
            "raw_boost": raw_boost,
            "capped_boost": capped_boost,
            "adjusted_threshold": adjusted,
            "final_threshold": final_threshold,
            "governance_applied": final_threshold != adjusted,
        }

        return final_threshold, metadata


# =============================================================================
# ADAPTIVE CONTEXT MANAGER (MAIN ORCHESTRATOR)
# =============================================================================

@dataclass
class AdaptiveContextResult:
    """Result from adaptive context processing."""
    raw_fidelity: float
    adjusted_fidelity: float
    message_type: MessageType
    conversation_phase: ConversationPhase
    adaptive_threshold: float
    should_intervene: bool
    context_embedding: Optional[np.ndarray]
    metadata: Dict[str, Any]

    @property
    def phase(self) -> ConversationPhase:
        return self.conversation_phase

    @property
    def drift_detected(self) -> bool:
        return self.should_intervene and self.adjusted_fidelity < self.adaptive_threshold


class AdaptiveContextManager:
    """
    Main orchestrator for the Adaptive Context System.

    Integrates message type classification, conversation phase detection,
    multi-tier context buffer, and adaptive threshold calculation.
    """

    def __init__(self, embedding_provider=None):
        self.embedding_provider = embedding_provider
        self.context_buffer = MultiTierContextBuffer()
        self.phase_detector = PhaseDetector()
        self.threshold_calculator = AdaptiveThresholdCalculator()
        self.turn_count = 0

    def process_message(
        self,
        user_input: str,
        input_embedding: np.ndarray,
        pa_embedding: np.ndarray,
        raw_fidelity: float,
        base_threshold: float = BASE_THRESHOLD
    ) -> AdaptiveContextResult:
        self.turn_count += 1

        recent_texts = self.context_buffer.get_recent_texts(n=3)
        topic_continuity = self._compute_topic_continuity(input_embedding)
        message_type = classify_message_type(
            user_input,
            recent_context=recent_texts,
            topic_continuity_score=topic_continuity
        )

        phase = self.phase_detector.update(raw_fidelity)

        adaptive_threshold, threshold_metadata = self.threshold_calculator.calculate_threshold(
            message_type=message_type,
            phase=phase,
            base_threshold=base_threshold
        )

        context_embedding = self.context_buffer.get_weighted_context_embedding()
        context_embeddings = self.context_buffer.get_all_context_embeddings()
        adjusted_fidelity = self._compute_adjusted_fidelity(
            input_embedding=input_embedding,
            pa_embedding=pa_embedding,
            context_embedding=context_embedding,
            raw_fidelity=raw_fidelity,
            message_type=message_type,
            context_embeddings=context_embeddings
        )

        should_intervene = adjusted_fidelity < adaptive_threshold

        self.context_buffer.add_message(
            text=user_input,
            embedding=input_embedding,
            fidelity_score=raw_fidelity,
            message_type=message_type
        )

        metadata = {
            **threshold_metadata,
            "turn_number": self.turn_count,
            "raw_fidelity": raw_fidelity,
            "adjusted_fidelity": adjusted_fidelity,
            "topic_continuity": topic_continuity,
        }

        return AdaptiveContextResult(
            raw_fidelity=raw_fidelity,
            adjusted_fidelity=adjusted_fidelity,
            message_type=message_type,
            conversation_phase=phase,
            adaptive_threshold=adaptive_threshold,
            should_intervene=should_intervene,
            context_embedding=context_embedding,
            metadata=metadata
        )

    def _compute_topic_continuity(self, current_embedding: np.ndarray) -> Optional[float]:
        context_embedding = self.context_buffer.get_weighted_context_embedding()
        if context_embedding is None:
            return None
        current_norm = current_embedding / np.linalg.norm(current_embedding)
        context_norm = context_embedding / np.linalg.norm(context_embedding)
        return float(np.dot(current_norm, context_norm))

    def _compute_adjusted_fidelity(
        self,
        input_embedding: np.ndarray,
        pa_embedding: np.ndarray,
        context_embedding: Optional[np.ndarray],
        raw_fidelity: float,
        message_type: MessageType,
        context_embeddings: Optional[List[np.ndarray]] = None
    ) -> float:
        input_norm = input_embedding / np.linalg.norm(input_embedding)

        context_similarity = 0.0
        best_turn_idx = -1

        if context_embeddings and len(context_embeddings) > 0:
            similarities = []
            for i, turn_emb in enumerate(context_embeddings):
                turn_norm = turn_emb / np.linalg.norm(turn_emb)
                sim = float(np.dot(input_norm, turn_norm))
                similarities.append(sim)
            context_similarity = max(similarities)
            best_turn_idx = similarities.index(context_similarity)
        elif context_embedding is not None:
            context_norm = context_embedding / np.linalg.norm(context_embedding)
            context_similarity = float(np.dot(input_norm, context_norm))
        else:
            return raw_fidelity

        MAX_CONTEXT_BOOST = 0.30
        BASE_CONTEXT_WEIGHT = 0.50

        MESSAGE_TYPE_MULTIPLIERS = {
            MessageType.ANAPHORA: 1.5,
            MessageType.CLARIFICATION: 1.4,
            MessageType.FOLLOW_UP: 1.0,
            MessageType.DIRECT: 0.7,
        }

        LOCAL_TYPE_THRESHOLDS = {
            MessageType.ANAPHORA: 0.15,
            MessageType.CLARIFICATION: 0.20,
            MessageType.FOLLOW_UP: 0.20,
            MessageType.DIRECT: 0.35,
        }

        type_multiplier = MESSAGE_TYPE_MULTIPLIERS.get(message_type, 1.0)
        context_threshold = LOCAL_TYPE_THRESHOLDS.get(message_type, 0.35)

        sci_adjusted = None
        has_prev = self.context_buffer.has_previous_turn()

        if SCI_ENABLED and has_prev:
            prev_embeddings, prev_fidelity = self.context_buffer.get_previous_turn_data()

            if prev_embeddings and prev_fidelity is not None:
                SHORT_PHRASE_TYPES = {MessageType.FOLLOW_UP, MessageType.ANAPHORA}
                SHORT_PHRASE_MIN_PREV_FIDELITY = 0.50
                SHORT_PHRASE_DECAY = 0.95

                if message_type in SHORT_PHRASE_TYPES and prev_fidelity >= SHORT_PHRASE_MIN_PREV_FIDELITY:
                    inherited = prev_fidelity * SHORT_PHRASE_DECAY
                    if inherited > raw_fidelity:
                        return min(inherited, 1.0)

                continuity_score, best_idx = calculate_semantic_continuity(
                    input_embedding, prev_embeddings
                )

                inherited_result, method = apply_continuity_inheritance(
                    raw_fidelity, continuity_score, prev_fidelity
                )

                if method != "direct_only":
                    sci_adjusted = inherited_result

        if context_similarity < context_threshold:
            if SCI_ENABLED and sci_adjusted is not None and sci_adjusted > raw_fidelity:
                return min(sci_adjusted, 1.0)
            return raw_fidelity

        excess_similarity = context_similarity - context_threshold
        max_excess = 1.0 - context_threshold
        normalized_excess = excess_similarity / max_excess

        semantic_boost = normalized_excess * MAX_CONTEXT_BOOST * BASE_CONTEXT_WEIGHT * type_multiplier
        context_attractor_result = raw_fidelity + semantic_boost

        if context_attractor_result - raw_fidelity > MAX_CONTEXT_BOOST:
            context_attractor_result = raw_fidelity + MAX_CONTEXT_BOOST

        context_attractor_result = min(context_attractor_result, 1.0)

        if SCI_ENABLED and sci_adjusted is not None and sci_adjusted > 0:
            adjusted = max(context_attractor_result, sci_adjusted)
        else:
            adjusted = context_attractor_result

        return adjusted

    def reset(self):
        self.context_buffer.clear()
        self.phase_detector.reset()
        self.turn_count = 0
