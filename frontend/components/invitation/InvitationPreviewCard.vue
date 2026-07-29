<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
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
  acceptanceScreen?: InvitationScreenEditForm | null
  allowReset?: boolean
  authorName?: string
  initialStatus?: InvitationResponseStatus
  message?: string
  planningContext?: boolean
  previewOnly?: boolean
  continueDisabled?: boolean
  recipientName?: string
  screen?: InvitationScreenEditForm | null
}

const props = withDefaults(defineProps<Props>(), {
  acceptanceScreen: null,
  allowReset: true,
  authorName: '',
  initialStatus: 'pending',
  message: '',
  planningContext: false,
  previewOnly: false,
  continueDisabled: false,
  recipientName: '',
  screen: null,
})
const emit = defineEmits<{
  answered: [status: FinalInvitationResponseStatus]
  continue: []
}>()

const config = useRuntimeConfig()
const answer = ref<Answer>(invitationStatusToAnswer(props.initialStatus ?? 'pending'))
const secondChance = ref(false)
const resultHeadingRef = ref<HTMLElement | null>(null)
const componentId = useId()
const questionId = `${componentId}-question`
const resultId = `${componentId}-result`
const runawayHelpId = `${componentId}-runaway-help`
const activeScreen = computed(() => (
  answer.value === 'accepted' && props.acceptanceScreen
    ? props.acceptanceScreen
    : props.screen
))
const illustration = computed(() => (
  activeScreen.value ? getInvitationImageByKey(activeScreen.value.image_key) : undefined
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
const acceptanceTitle = computed(() => props.acceptanceScreen?.title.trim() ?? '')
const acceptanceSubtitle = computed(() => props.acceptanceScreen?.subtitle.trim() ?? '')
const acceptanceButtonText = computed(() => (
  props.acceptanceScreen?.button_text.trim() || 'Продолжить'
))
const acceptanceFallbackCopy = computed(() => {
  if (!props.planningContext) {
    return 'Похоже, впереди прекрасная встреча.'
  }

  return props.acceptanceScreen
    ? 'Нажми «Продолжить», чтобы перейти к выбору даты и активности.'
    : 'Сохраняем ответ и открываем следующий этап планирования.'
})

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

function continuePlanning(): void {
  if (props.previewOnly || props.continueDisabled) {
    return
  }

  emit('continue')
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
    :aria-labelledby="answer === null ? questionId : resultId"
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
        :id="questionId"
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
          :tabindex="previewOnly ? -1 : undefined"
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
          :tabindex="previewOnly ? -1 : undefined"
          :aria-label="previewOnly
            ? `Предпросмотр кнопки: ${noButtonText}`
            : secondChance
              ? `${noButtonText}, всё же отклонить приглашение`
              : `${noButtonText}, отклонить приглашение`"
          :aria-describedby="previewOnly ? undefined : runawayHelpId"
          :style="noButtonStyle"
          @pointerenter="handleNoPointerEnter"
          @click="handleNoClick"
        >
          {{ noButtonText }}
        </button>

        <p v-if="!previewOnly" :id="runawayHelpId" class="sr-only">
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
        :id="resultId"
        ref="resultHeadingRef"
        class="invitation-card__result-title"
        tabindex="-1"
      >
        <template v-if="answer === 'accepted'">
          {{ acceptanceTitle || 'Ура! Кажется, свиданию быть 💘' }}
        </template>
        <template v-else>
          Очень жаль 😢
        </template>
      </h2>
      <p class="invitation-card__result-copy">
        {{ answer === 'accepted'
          ? acceptanceSubtitle || acceptanceFallbackCopy
          : 'Спланируем в другой раз 😉' }}
      </p>
      <button
        v-if="answer === 'accepted' && props.acceptanceScreen"
        class="invitation-card__continue-button"
        type="button"
        :tabindex="previewOnly ? -1 : undefined"
        :aria-label="previewOnly
          ? `Предпросмотр кнопки: ${acceptanceButtonText}`
          : acceptanceButtonText"
        :disabled="props.continueDisabled"
        @click="continuePlanning"
      >
        {{ acceptanceButtonText }}
      </button>
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
