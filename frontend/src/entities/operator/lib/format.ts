export function formatDateTime(value: string | null): string {
  if (value === null) {
    return "Нет данных";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatActiveStatus(isActive: boolean): string {
  return isActive ? "Активен" : "Отключён";
}

export function formatLoginResult(success: boolean): string {
  return success ? "Успешно" : "Ошибка";
}

export function formatFailureReason(reason: string | null): string {
  if (reason === "invalid_credentials") {
    return "Неверные данные";
  }
  if (reason === "inactive_user") {
    return "Пользователь отключён";
  }
  return "Нет";
}
