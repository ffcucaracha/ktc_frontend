import { Alert, Stack } from "@mui/material";

import {
  useOperatorRecommendationsQuery,
  useOperatorSkillProfileQuery,
  useOperatorTrainingResultsQuery,
} from "../../entities/training/model/queries";
import { OperatorRecommendationCard } from "../operator-recommendation/OperatorRecommendationCard";
import { OperatorSkillProfile } from "../operator-skill-profile/OperatorSkillProfile";
import { OperatorTrainingHistory } from "../operator-training-history/OperatorTrainingHistory";

interface OperatorTrainingAnalyticsProps {
  operatorId: string;
}

export function OperatorTrainingAnalytics({ operatorId }: OperatorTrainingAnalyticsProps): JSX.Element {
  const resultsQuery = useOperatorTrainingResultsQuery(operatorId);
  const skillQuery = useOperatorSkillProfileQuery(operatorId);
  const recommendationsQuery = useOperatorRecommendationsQuery(operatorId);

  return (
    <Stack spacing={2}>
      {resultsQuery.isError || skillQuery.isError || recommendationsQuery.isError ? (
        <Alert severity="warning">
          Часть учебной аналитики временно недоступна. Управление оператором и история входов не затронуты.
        </Alert>
      ) : null}

      {resultsQuery.isLoading ? (
        <Alert severity="info">Загружаем статистику тренировок…</Alert>
      ) : resultsQuery.data !== undefined ? (
        <OperatorTrainingHistory results={resultsQuery.data} />
      ) : null}

      {skillQuery.isLoading ? (
        <Alert severity="info">Загружаем профиль навыков…</Alert>
      ) : skillQuery.data !== undefined ? (
        <OperatorSkillProfile profile={skillQuery.data} />
      ) : null}

      {recommendationsQuery.isLoading ? (
        <Alert severity="info">Формируем персональную рекомендацию…</Alert>
      ) : recommendationsQuery.data !== undefined ? (
        <OperatorRecommendationCard data={recommendationsQuery.data} />
      ) : null}
    </Stack>
  );
}
