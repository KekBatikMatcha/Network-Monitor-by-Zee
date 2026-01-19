<?php
header('Content-Type: application/json; charset=utf-8');

$base = realpath(__DIR__ . '/..');
$dataPath = $base . DIRECTORY_SEPARATOR . 'data' . DIRECTORY_SEPARATOR . 'status.json';

if (!file_exists($dataPath)) {
  echo json_encode(["ok"=>false, "error"=>"status.json not found"]);
  exit;
}

$json = file_get_contents($dataPath);
$data = json_decode($json, true);

if (!is_array($data)) {
  echo json_encode(["ok"=>false, "error"=>"Invalid JSON in status.json"]);
  exit;
}

echo json_encode([
  "ok" => true,
  "updated_at" => gmdate("c"),
  "items" => array_values($data)
]);
