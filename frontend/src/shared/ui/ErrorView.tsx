import { Alert, AlertTitle, Box, Button, Stack, Typography } from "@mui/material";

interface ErrorViewProps {
  title?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function ErrorView({
  title = "Ошибка",
  message,
  actionLabel,
  onAction,
}: ErrorViewProps): JSX.Element {
  return (
    <Box sx={{ py: 3 }}>
      <Alert severity="error">
        <AlertTitle>{title}</AlertTitle>
        <Stack spacing={2}>
          <Typography>{message}</Typography>
          {actionLabel !== undefined && onAction !== undefined ? (
            <Button variant="outlined" color="inherit" onClick={onAction}>
              {actionLabel}
            </Button>
          ) : null}
        </Stack>
      </Alert>
    </Box>
  );
}
