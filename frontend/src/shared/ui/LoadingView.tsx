import { Box, CircularProgress, Stack, Typography } from "@mui/material";

interface LoadingViewProps {
  message?: string;
}

export function LoadingView({ message = "Загрузка" }: LoadingViewProps): JSX.Element {
  return (
    <Box sx={{ display: "grid", minHeight: "60vh", placeItems: "center" }}>
      <Stack alignItems="center" spacing={2} role="status" aria-live="polite">
        <CircularProgress aria-label={message} />
        <Typography color="text.secondary">{message}</Typography>
      </Stack>
    </Box>
  );
}
