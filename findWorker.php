<?php
$directories = array();

$thisFile = $argv[1];
$dir = $argv[2];
$dateString = $argv[3];
$file = $argv[4];

// run exiftool
exec("z:\\exiftool.exe \"" . $thisFile . "\" 2>&1", $probe, $returnValue);
						
// pull out the modify date
$thisDate = getExifCreateDate($thisFile, $probe, $dateString);
						
$thisFolderYear = "E:\\photos\\" . date('Y', $thisDate);
if ( directoryCheck($thisFolderYear) )
{
	$thisFolderMonth = "E:\\photos\\" . date('Y', $thisDate) . "\\" . date('m', $thisDate);
							
	if ( directoryCheck($thisFolderMonth) )
	{
		// directory is good to go
		fileMove($thisFile, $file, $thisFolderMonth);
		
	} else {
		// this should never trigger...
		
		
	}
	
} else {
	// this should never trigger...
	
	
}

function fileMove($thisFile, $fileName, $tobeFolder)
{
	// if the file exists, hash it to compare
	// if its the same, just delete the source
	// if its different, take the larger one
	// if its different but the size is the same, add a guid to the end
	
	// file exists in destination
	if ( file_exists($tobeFolder . "\\" . $fileName) )
	{
		// hash it
		
		// source file hash
		$sourceHash = hash_file("sha1", $thisFile);
		
		// destination file hash
		$destinationHash = hash_file("sha1", $tobeFolder . "\\" . $fileName);
		
		// are they the same file?
		if ( $sourceHash == $destinationHash )
		{
			// just delete the source
			if (unlink($thisFile) )
			{
				addLog($thisFile . " - destination exists with same content at " . $tobeFolder . "\\" . $fileName . ".  Deleted source");
				return true;
				
			} else{
				addLog($thisFile . " - destination exists with same content at " . $tobeFolder . "\\" . $fileName . ".  Unable to delete source");
				die;
				
			}
			
		} else {
			// file contents are different
			if ( filesize($thisFile) > filesize($tobeFolder . "\\" . $fileName) )
			{
				// source is larger				
				// move source
				if ( rename($thisFile, $tobeFolder . "\\" . $fileName) )
				{
					// successfully moved
					addLog($thisFile . " - file exists at " . $tobeFolder . "\\" . $fileName . " but source is larger.  Replaced with source");
					return true;
					
				} else{
					//failed to copy
					addLog($thisFile . " - unable to move to " . $tobeFolder . "\\" . $fileName);
					return false;
					
				}
				
			} elseif ( filesize($thisFile) < filesize($tobeFolder . "\\" . $fileName) )
			{
				// destination is larger
				// just delete the source
				if (unlink($thisFile) )
				{
					addLog($thisFile . " - file exists at " . $tobeFolder . "\\" . $fileName . " and destination is larger.  Deleted source");
					return true;
					
				} else{
					addLog($thisFile . " - file exists at " . $tobeFolder . "\\" . $fileName . ".  Unable to delete source");
					die;
					
				}
			
			} else {
				// they are the same size
				
				// find the .
				//$extension = strtoupper(substr($thisFile, -3));
				
				addLog($thisFile . " - file exists at " . $tobeFolder . "\\" . $fileName . ".  Both are the same size but differ in content.  Copying source and changing filename to something new");
				die;
				
			}
			
		}
		
	} else {
		// file doesn't exist
		if ( rename($thisFile, $tobeFolder . "\\" . $fileName) )
		{
			// successfully moved
			addLog($thisFile . " - successfully moved to " . $tobeFolder . "\\" . $fileName);
			return true;
			
		} else {
			//failed to copy
			addLog($thisFile . " - unable to move to " . $tobeFolder . "\\" . $fileName);
			return false;
			
		}

	}
	
	return false;
	
}

function generateRandomString($length = 10) {
    $characters = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
    $charactersLength = strlen($characters);
    $randomString = '';
    for ($i = 0; $i < $length; $i++) {
        $randomString .= $characters[rand(0, $charactersLength - 1)];
    }
    return $randomString;
}



function directoryCheck($thisDirectory)
{
	global $directories;
	for ( $i=0; $i<count($directories); $i++ )
	{
		if ( $directories[$i] == $thisDirectory )
		{
			return true;
			
		}
		
	}
	
	if ( is_dir($thisDirectory) )
	{
		$directories[count($directories)] = $thisDirectory;
		return true;
		
	} else{
		if ( mkdir($thisDirectory) )
		{
			$directories[count($directories)] = $thisDirectory;
			return true;
			
		} else{
			addLog($thisDirectory . " - did not exist and creation failed");
			die;
			
		}
		
	}
	
	// this should never trigger
	return false;
	
}

function getExifCreateDate($thisFile, $probe, $dateString)
{	
	for ( $j=0; $j < count($probe); $j++ )
	{
		$cTime = strpos($probe[$j], $dateString);
		
		if ( $cTime !== false )
		{
			$delimitLocation = strpos($probe[$j], ":");
			
			if ( $delimitLocation !== false )
			{
				$rawDate = trim(substr($probe[$j], $delimitLocation+1));
				
				$time = strtotime($rawDate);
				//$newformat = date('Y-m-d', $time);
								
				return $time;
								
			} else {
				// couldn't find : in date string.  Fall back on file modify date
				addLog($thisFile . " - couldn't find : in date string.  Raw string: " . $probe[$j] . ".  Falling back to file modify date.");
				return getFileModifyDate($thisFile, $probe);
				
			}
			
		}
		
	}
	
	// function will end before here if it worked
	// couldn't find date string	
	// fall back on file modify date
	// will push back false if this fails too
	addLog($thisFile . " - couldn't find EXIF modify date.  Falling back to file modify date");
	return getFileModifyDate($thisFile, $probe);
	
}

function getFileModifyDate($thisFile, $probe)
{
	for ( $j=0; $j < count($probe); $j++ )
	{
		$cTime = strpos($probe[$j], "File Modification Date");
		
		if ( $cTime !== false )
		{
			$delimitLocation = strpos($probe[$j], ":");
			
			if ( $delimitLocation !== false )
			{
				$rawDate = trim(substr($probe[$j], $delimitLocation+1));
				$time = strtotime($rawDate);
				return $time;
				
				//return date('Y-m-d', $time);
								
			} else {
				// couldn't find : in date string.  Fall back on file modify date
				addLog($thisFile . " - couldn't find : in file modify date string.  Raw string: " . $probe[$j]);
				return false;
				
			}
			
		}
		
	}
	
	// function will end before here if it worked
	// couldn't find date string
	addLog($thisFile . " - couldn't find a file modify date date in the exif data");
	
	// fall back on file modify date
	return false;

}

function addLog($message)
{
	global $log;
	global $fLog;
	//$message .= "\r\n";
	echo "LOG: " . $message;
	$log .= $message;
	
	$fLog = fopen("e:\photolog.log", "a");
	fwrite($fLog, $message);
	fclose($fLog);	
	
}


?>