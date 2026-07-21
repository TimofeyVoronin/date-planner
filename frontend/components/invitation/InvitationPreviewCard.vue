<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { RUNAWAY_ATTEMPT_LIMIT, useRunawayButton } from '../../composables/useRunawayButton'

type Answer = 'accepted' | 'declined' | null

const answer = ref<Answer>(null)
const resultHeadingRef = ref<HTMLElement | null>(null)

const {
  attempts,
  canRunAway,
  containerRef,
  noButtonRef,
  noButtonStyle,
  prefersReducedMotion,
  resetRunawayButton,
  runAway,
  yesButtonRef,
  yesButtonStyle,
} = useRunawayButton()

function focusResult(): void {
  void nextTick(() => resultHeadingRef.value?.focus())
}

function acceptInvitation(): void {
  answer.value = 'accepted'
  focusResult()
}

function declineInvitation(): void {
  answer.value = 'declined'
  focusResult()
}

function handleNoPointerEnter(event: PointerEvent): void {
  if (event.pointerType === 'mouse') {
    runAway()
  }
}

function handleNoClick(event: MouseEvent): void {
  if (event.detail === 0 || !canRunAway.value) {
    declineInvitation()
    return
  }

  if (runAway()) {
    event.preventDefault()
    return
  }

  declineInvitation()
}

function resetDemo(): void {
  answer.value = null
  resetRunawayButton()
  void nextTick(() => yesButtonRef.value?.focus())
}
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
      <p class="invitation-card__note">Для тебя — с теплом</p>
      <h2 id="invitation-question" class="invitation-card__question">
        Ты пойдёшь со мной<br>на свидание?
      </h2>

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
          aria-label="Нет, отклонить приглашение"
          aria-describedby="runaway-help"
          :style="noButtonStyle"
          @pointerenter="handleNoPointerEnter"
          @click="handleNoClick"
        >
          Нет
        </button>

        <p id="runaway-help" class="sr-only">
          Для мыши и сенсорного экрана кнопка может переместиться до пяти раз.
          С клавиатуры ответ доступен сразу.
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
          Ответ принят. Никакого давления 🙂
        </template>
      </h2>
      <p class="invitation-card__result-copy">
        {{ answer === 'accepted'
          ? 'Следующим шагом здесь появится совместное планирование.'
          : 'Главное — честный и комфортный ответ.' }}
      </p>
      <button
        class="invitation-card__reset-button"
        type="button"
        aria-label="Вернуть демонстрацию в начальное состояние"
        @click="resetDemo"
      >
        Посмотреть ещё раз
      </button>
    </div>
  </article>
</template>
