import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface MailMessage {
  id: string
  subject: string
  sender: string
  preview: string
  receivedAt: string
  isRead: boolean
}

export interface AiTask {
  id: string
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
  sourceMailId: string
  confirmed: boolean
}

export const useMailStore = defineStore('mail', () => {
  const mails = ref<MailMessage[]>([])
  const selectedMail = ref<MailMessage | null>(null)
  const generatedTasks = ref<AiTask[]>([])
  const isScanning = ref(false)

  function setMails(list: MailMessage[]) {
    mails.value = list
  }

  function selectMail(mail: MailMessage) {
    selectedMail.value = mail
  }

  function addTask(task: AiTask) {
    generatedTasks.value.push(task)
  }

  function confirmTask(taskId: string) {
    const task = generatedTasks.value.find(t => t.id === taskId)
    if (task) task.confirmed = true
  }

  function setScanning(v: boolean) {
    isScanning.value = v
  }

  return {
    mails,
    selectedMail,
    generatedTasks,
    isScanning,
    setMails,
    selectMail,
    addTask,
    confirmTask,
    setScanning
  }
})
