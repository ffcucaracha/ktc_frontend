import { Box, LinearProgress, Paper, Stack, Typography } from "@mui/material";

import type { OperatorSkillProfile as SkillProfile } from "../../entities/training/api/types";

const labels: Record<string, string> = {
  pump_control: "Управление насосами",
  regulation: "Регулирование",
  alarm_handling: "Работа с сигналами",
  reaction_speed: "Скорость реакции",
  procedure_sequence: "Последовательность операций",
  emergency_response: "Аварийное реагирование",
};

interface OperatorSkillProfileProps {
  profile: SkillProfile;
}

function scoreLabel(value: number | null): string {
  return value === null ? "не оценено" : `${value.toFixed(0)} / 100`;
}

export function OperatorSkillProfile({ profile }: OperatorSkillProfileProps): JSX.Element {
  const skills = [
    ["procedure_sequence", profile.average_sequence_score],
    ["reaction_speed", profile.average_reaction_score],
    ["emergency_response", profile.average_safety_score],
  ] as const;

  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", p: 3 }}>
      <Stack spacing={2}>
        <Box>
          <Typography component="h3" variant="h6">Профиль навыков</Typography>
          <Typography color="text.secondary">
            Оценено сессий: {profile.assessed_sessions}. Слабая зона: {profile.weakest_skill === null ? "не определена" : (labels[profile.weakest_skill] ?? profile.weakest_skill)}.
          </Typography>
        </Box>
        {skills.map(([code, score]) => (
          <Box key={code}>
            <Stack direction="row" justifyContent="space-between" spacing={2}>
              <Typography>{labels[code] ?? code}</Typography>
              <Typography color="text.secondary">{scoreLabel(score)}</Typography>
            </Stack>
            <LinearProgress variant="determinate" value={score ?? 0} sx={{ mt: 0.75, height: 8, borderRadius: 4 }} />
          </Box>
        ))}
        <Typography variant="body2" color="text.secondary">
          Управление насосами, регулирование и работа с сигналами рассчитываются в backend-профиле по фактическим ошибкам; агрегированный API пока отдельно не отдаёт их числовые значения.
        </Typography>
      </Stack>
    </Paper>
  );
}
