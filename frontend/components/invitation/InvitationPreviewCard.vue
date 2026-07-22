<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { RUNAWAY_ATTEMPT_LIMIT, useRunawayButton } from '../../composables/useRunawayButton'
import type {
  FinalInvitationResponseStatus,
  InvitationResponseStatus,
} from '../../types/invitation'
import { invitationStatusToAnswer } from '../../utils/invitations'

type Answer = FinalInvitationResponseStatus | null

type Props = {
  allowReset?: boolean
  authorName?: string
  initialStatus?: InvitationResponseStatus
  message?: string
  recipientName?: string
}

const props = withDefaults(defineProps<Props>(), {
  allowReset: true,
  authorName: '',
  initialStatus: 'pending',
  message: '',
  recipientName: '',
})
const emit = defineEmits<{
  answered: [status: FinalInvitationResponseStatus]
}>()

const answer = ref<Answer>(invitationStatusToAnswer(props.initialStatus))
const secondChance = ref(false)
const resultHeadingRef = ref<HTMLElement | null>(null)

const {
  attempts,
  canRunAway,
  containerRef,
  noButtonRef,
  noButtonStyle,
  prefersReducedMotion,
  resetRunawayButton,
  runawayLimitReached,
  runAway,
  yesButtonRef,
  yesButtonStyle,
} = useRunawayButton()

function focusResult(): void {
  void nextTick(() => resultHeadingRef.value?.focus())
}

function chooseAnswer(status: FinalInvitationResponseStatus): void {
  answer.value = status
  emit('answered', status)
  focusResult()
}

function acceptInvitation(): void {
  chooseAnswer('accepted')
}

function declineInvitation(): void {
  chooseAnswer('declined')
}

function handleNoPointerEnter(event: PointerEvent): void {
  if (event.pointerType === 'mouse' && !secondChance.value) {
    if (runAway() && runawayLimitReached.value) {
      secondChance.value = true
    }
  }
}

function offerSecondChanceOrDecline(): void {
  if (!secondChance.value) {
    secondChance.value = true
    return
  }

  declineInvitation()
}

function handleNoClick(event: MouseEvent): void {
  if (secondChance.value) {
    declineInvitation()
    return
  }

  if (event.detail === 0 || prefersReducedMotion.value) {
    declineInvitation()
    return
  }

  if (!canRunAway.value) {
    offerSecondChanceOrDecline()
    return
  }

  if (runAway()) {
    event.preventDefault()

    if (runawayLimitReached.value) {
      secondChance.value = true
    }

    return
  }

  offerSecondChanceOrDecline()
}

function resetDemo(): void {
  answer.value = null
  secondChance.value = false
  resetRunawayButton()
  void nextTick(() => yesButtonRef.value?.focus())
}

watch(
  () => props.initialStatus,
  (status) => {
    answer.value = invitationStatusToAnswer(status)
    secondChance.value = false

    if (status === 'pending') {
      resetRunawayButton()
    }
    else {
      focusResult()
    }
  },
)
</script>

<template>
  <article
    class="invitation-card"
    :aria-labelledby="answer === null ? 'invitation-question' : 'invitation-result'"
  >
    <div class="invitation-card__illustration" aria-hidden="true">
      <span class="invitation-card__spark invitation-card__spark--left">✦</span>
      <img
        src="/images/envelope-heart.svg"
        alt=""
        width="230"
        height="170"
      >
      <span class="invitation-card__spark invitation-card__spark--right">✦</span>
    </div>

    <div v-if="answer === null" class="invitation-card__body">
      <p class="invitation-card__note">Для тебя с любовью</p>
      <h2
        id="invitation-question"
        class="invitation-card__question"
        :class="{ 'invitation-card__question--second-chance': secondChance }"
        aria-live="polite"
      >
        <span v-if="secondChance">
          Может всё таки да?
          <span class="invitation-card__sad-emoji" aria-hidden="true">😢</span>
        </span>
        <span v-else-if="props.recipientName">
          {{ props.recipientName }},<br>
          ты пойдёшь со мной<br>на свидание?
        </span>
        <span v-else>
          Ты пойдёшь со мной<br>на свидание?
        </span>
      </h2>

      <p v-if="props.message.trim()" class="invitation-card__personal-message">
        {{ props.message.trim() }}
      </p>
      <p v-if="props.authorName" class="invitation-card__signature">
        — {{ props.authorName }}
      </p>

      <div
        ref="containerRef"
        class="invitation-card__actions"
        :class="{ 'invitation-card__actions--reduced-motion': prefersReducedMotion }"
      >
        <button
          ref="yesButtonRef"
          class="invitation-card__yes-button"
          type="button"
          aria-label="Да, я пойду на свидание"
          :style="yesButtonStyle"
          @click="acceptInvitation"
        >
          <span class="invitation-card__yes-heart" aria-hidden="true">♥</span>
          <span>Да! 😍</span>
        </button>

        <button
          ref="noButtonRef"
          class="invitation-card__no-button"
          type="button"
          :aria-label="secondChance
            ? 'Нет, всё же отклонить приглашение'
            : 'Нет, отклонить приглашение'"
          aria-describedby="runaway-help"
          :style="noButtonStyle"
          @pointerenter="handleNoPointerEnter"
          @click="handleNoClick"
        >
          Нет
        </button>

        <p id="runaway-help" class="sr-only">
          Для мыши и сенсорного экрана кнопка может переместиться до пяти раз.
          После пятой попытки появится повторный вопрос. С клавиатуры ответ доступен сразу.
        </p>
        <p class="sr-only" aria-live="polite">
          Попыток перемещения: {{ attempts }} из {{ RUNAWAY_ATTEMPT_LIMIT }}.
        </p>
      </div>
    </div>

    <div v-else class="invitation-card__result" aria-live="polite">
      <span class="invitation-card__result-icon" aria-hidden="true">
        {{ answer === 'accepted' ? '💘' : '🌷' }}
      </span>
      <h2
        id="invitation-result"
        ref="resultHeadingRef"
        class="invitation-card__result-title"
        tabindex="-1"
      >
        <template v-if="answer === 'accepted'">
          Ура! Теперь давай спланируем идеальное свидание 💘
        </template>
        <template v-else>
          Очень жаль 😢
        </template>
      </h2>
      <p class="invitation-card__result-copy">
        {{ answer === 'accepted'
          ? 'Следующим шагом здесь появится совместное планирование.'
          : 'Спланируем в другой раз 😉' }}
      </p>
      <button
        v-if="props.allowReset"
        class="invitation-card__reset-button"
        type="button"
        :aria-label="props.recipientName
          ? 'Вернуть приглашение в начальное состояние'
          : 'Вернуть демонстрацию в начальное состояние'"
        @click="resetDemo"
      >
        Посмотреть ещё раз
      </button>
    </div>
  </article>
</template>
