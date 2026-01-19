<?php
header('Content-Type: application/json; charset=utf-8');

$limit = isset($_GET['limit']) ? max(1, min(200, (int)$_GET['limit'])) : 25;

$base = realpath(__DIR__ . '/..');
$path = $base . DIRECTORY_SEPARATOR . 'data' . DIRECTORY_SEPARATOR . 'alerts.jsonl';

if (!file_exists($path)) {
  echo json_encode(["ok"=>true, "items"=>[]]);
  exit;
}

$lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
if (!$lines) {
  echo json_encode(["ok"=>true, "items"=>[]]);
  exit;
}

$lines = array_slice($lines, -$limit);
$items = [];
foreach ($lines as $ln) {
  $obj = json_decode($ln, true);
  if (is_array($obj)) $items[] = $obj;
}
echo json_encode(["ok"=>true, "items"=>$items]);
