<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RUNAWAY_ATTEMPT_LIMIT, useRunawayButton } from '../../composables/useRunawayButton'
import type {
  FinalInvitationResponseStatus,
  InvitationResponseStatus,
} from '../../types/invitation'
import type { InvitationScreenEditForm } from '../../types/screen'
import { getInvitationImageByKey, resolveInvitationImageUrl } from '../../utils/invitationImages'
import { invitationStatusToAnswer } from '../../utils/invitations'

type Answer = FinalInvitationResponseStatus | null

type Props = {
  allowReset?: boolean
  authorName?: string
  initialStatus?: InvitationResponseStatus
  message?: string
  planningContext?: boolean
  previewOnly?: boolean
  recipientName?: string
  screen?: InvitationScreenEditForm | null
}

const props = withDefaults(defineProps<Props>(), {
  allowReset: true,
  authorName: '',
  initialStatus: 'pending',
  message: '',
  planningContext: false,
  previewOnly: false,
  recipientName: '',
  screen: null,
})
const emit = defineEmits<{
  answered: [status: FinalInvitationResponseStatus]
}>()

const config = useRuntimeConfig()
const answer = ref<Answer>(invitationStatusToAnswer(props.initialStatus ?? 'pending'))
const secondChance = ref(false)
const resultHeadingRef = ref<HTMLElement | null>(null)
const illustration = computed(() => (
  props.screen ? getInvitationImageByKey(props.screen.image_key) : undefined
))
const illustrationUrl = computed(() => (
  illustration.value
    ? resolveInvitationImageUrl(illustration.value.assetPath, config.app.baseURL)
    : '/images/envelope-heart.svg'
))
const invitationTitle = computed(() => props.screen?.title.trim() ?? '')
const invitationSubtitle = computed(() => props.screen?.subtitle.trim() ?? '')
const yesButtonText = computed(() => props.screen?.button_text.trim() || 'Да! 😍')
const noButtonText = computed(() => props.screen?.secondary_button_text.trim() || 'Нет')

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
  if (props.previewOnly) {
    return
  }

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
  if (props.previewOnly) {
    return
  }

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
  if (props.previewOnly) {
    event.preventDefault()
    return
  }

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
    answer.value = invitationStatusToAnswer(status ?? 'pending')
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
    :class="{ 'invitation-card--preview-only': previewOnly }"
    :aria-labelledby="answer === null ? 'invitation-question' : 'invitation-result'"
  >
    <div
      class="invitation-card__illustration"
      :class="{ 'invitation-card__illustration--library': illustration }"
      :aria-hidden="illustration ? undefined : 'true'"
    >
      <span v-if="!illustration" class="invitation-card__spark invitation-card__spark--left">✦</span>
      <img
        :src="illustrationUrl"
        :alt="illustration?.altText ?? ''"
        width="640"
        height="420"
      >
      <span v-if="!illustration" class="invitation-card__spark invitation-card__spark--right">✦</span>
    </div>

    <div v-if="answer === null" class="invitation-card__body">
      <p class="invitation-card__note">Для тебя с любовью</p>
      <h2
        id="invitation-question"
        class="invitation-card__question"
        :class="{ 'invitation-card__question--second-chance': secondChance }"
        aria-live="polite"
      >
        <span v-if="secondChance && !previewOnly">
          Может всё таки да?
          <span class="invitation-card__sad-emoji" aria-hidden="true">😢</span>
        </span>
        <span v-else-if="invitationTitle">{{ invitationTitle }}</span>
        <span v-else-if="props.recipientName">
          {{ props.recipientName }},<br>
          ты пойдёшь со мной<br>на свидание?
        </span>
        <span v-else>
          Ты пойдёшь со мной<br>на свидание?
        </span>
      </h2>

      <p v-if="invitationSubtitle" class="invitation-card__screen-subtitle">
        {{ invitationSubtitle }}
      </p>
      <p v-if="props.message.trim()" class="invitation-card__personal-message">
        {{ props.message.trim() }}
      </p>
      <p v-if="props.authorName" class="invitation-card__signature">
        — {{ props.authorName }}
      </p>

      <div
        ref="containerRef"
        class="invitation-card__actions"
        :class="{
          'invitation-card__actions--reduced-motion': prefersReducedMotion,
          'invitation-card__actions--preview-only': previewOnly,
        }"
      >
        <button
          ref="yesButtonRef"
          class="invitation-card__yes-button"
          type="button"
          :aria-label="previewOnly ? `Предпросмотр кнопки: ${yesButtonText}` : yesButtonText"
          :style="yesButtonStyle"
          @click="acceptInvitation"
        >
          <span class="invitation-card__yes-heart" aria-hidden="true">♥</span>
          <span>{{ yesButtonText }}</span>
        </button>

        <button
          ref="noButtonRef"
          class="invitation-card__no-button"
          type="button"
          :aria-label="previewOnly
            ? `Предпросмотр кнопки: ${noButtonText}`
            : secondChance
              ? `${noButtonText}, всё же отклонить приглашение`
              : `${noButtonText}, отклонить приглашение`"
          :aria-describedby="previewOnly ? undefined : 'runaway-help'"
          :style="noButtonStyle"
          @pointerenter="handleNoPointerEnter"
          @click="handleNoClick"
        >
          {{ noButtonText }}
        </button>

        <p v-if="!previewOnly" id="runaway-help" class="sr-only">
          Для мыши и сенсорного экрана кнопка может переместиться до пяти раз.
          После пятой попытки появится повторный вопрос. С клавиатуры ответ доступен сразу.
        </p>
        <p v-if="!previewOnly" class="sr-only" aria-live="polite">
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
          Ура! Кажется, свиданию быть 💘
        </template>
        <template v-else>
          Очень жаль 😢
        </template>
      </h2>
      <p class="invitation-card__result-copy">
        {{ answer === 'accepted'
          ? props.planningContext
            ? 'Продолжение ниже: выбери вариант или посмотри уже подтверждённый план.'
            : 'Похоже, впереди прекрасная встреча.'
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
