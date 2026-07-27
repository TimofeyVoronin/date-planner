<script setup lang="ts">
import type { InvitationScreenRecord } from '../../types/screen'
import { FINAL_TEMPLATE_VARIABLES } from '../../utils/finalTemplates'

const props = defineProps<{
  screen: InvitationScreenRecord
}>()

const formatTemplateVariable = (variable: string): string => `{${variable}}`
</script>

<template>
  <section class="builder-final-template" aria-labelledby="builder-final-template-title">
    <header>
      <span aria-hidden="true">🧩</span>
      <div>
        <p>Безопасный шаблон</p>
        <h3 id="builder-final-template-title">Финальный текст уже готов к подстановке данных</h3>
      </div>
    </header>

    <p>
      В шаблоне разрешены только заранее определённые переменные. Они заменяются обычным
      текстом и не могут выполнять код, обращаться к полям объектов или применять форматирование.
    </p>

    <code class="builder-final-template__value">{{ props.screen.template_text }}</code>

    <div>
      <strong>Доступные переменные</strong>
      <ul class="builder-final-template__variables" aria-label="Разрешённые переменные шаблона">
        <li v-for="variable in FINAL_TEMPLATE_VARIABLES" :key="variable">
          <code>{{ formatTemplateVariable(variable) }}</code>
        </li>
      </ul>
    </div>

    <p class="builder-final-template__notice">
      В DPL-502 здесь появятся редактирование текста, изображения и остальных настроек
      финального экрана. Сейчас можно проверить итоговую подстановку в предпросмотре справа.
    </p>
  </section>
</template>
