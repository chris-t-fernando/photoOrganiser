<?php 
$log = "";
$directories = array();

read_directory($argv[1], 0);

function read_directory($dir, $recursion)
{	
	$done = 0;
	$files = scandir($dir);
	$filecount = count($files);
	for ($i=0; $i < $filecount ; $i++)
	{
		
		if ( $files[$i] != "." && $files[$i] != ".." )
		{
			$thisFile = $dir . "\\" . $files[$i];
			if ( is_dir($thisFile) )
			{	
				read_directory($thisFile, ($recursion+1));
				
			}
			elseif ( is_file($thisFile) )
			{
				if ( filesize($thisFile) === 0 )
				{
					// dead file
					addLog($thisFile . " - has zero content.  Ignored.");
				
				} elseif ( $thisFile[0] == "." )
				{
					addLog($thisFile . " - .filename (system file).  Ignored.");
				
				} else {
					// MOV		Create Date
					// HEIC		Create Date
					// PNG		Date Created
					// JPG		Create Date
					// MP4		Create Date

					// todo: don't be lazy and search for the .
					$extension = strtoupper(substr($thisFile, -3));
					
					if ( $extension == "PNG" )
					{
						$dateString = "Date Created";
					}
					elseif ( $extension == "AVI" )
					{
						$dateString = "Date/Time Original";
					}
					//PEG for JPEG, EIC for HEIC
					elseif (
						( $extension == "MOV" ) ||
						( $extension == "EIC") ||
						( $extension == "JPG") ||
						( $extension == "PEG") ||
						( $extension == "MP4" ) ||
						( $extension == "3GP" )
					)
					{
						$dateString = "Create Date";
					}
					else {
						// this is some other weird file - write it to a log
						addLog($thisFile . " - unknown file. File size is " . round(filesize($thisFile)/1024/1024,1) . "MB.  Ignored.");
						unset($extension);
						
					}
					
					// if its a valid file
					if ( isset($extension) )
					{
						// call the php to call exiftool but background the task
						$cmd = "php.exe findWorker.php \"" . $thisFile . "\" \"" . $dir . "\" \"" . $dateString . "\" \"" . $files[$i] . "\"";
						pclose(popen("start /B ". $cmd, "r"));
						
						$done++;
						
						if ( ($done % 15) == 0 )
						{
							echo "Up to folder " . $dir . " and modified date " . date("Y-m-d", filemtime($thisFile)) . "\r\n";
							sleep(15);
							
						}

					}
					
				}
				
			}
			
		}
		
    }
	
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
//	global $log;
//	global $fLog;
//	$message .= "\r\n";
//	echo "LOG: " . $message;
//	$log .= $message;
//	fwrite($fLog, $message);
}

?>